# frozen_string_literal: true

BOOTSTRAP_PATH = "/usr/src/redmine/bootstrap_redmine.rb"
TRACKER_NAMES = ["問い合わせ", "報告書", "客先同行"].freeze
LEGACY_FIELD_NAMES = ["報告書要否", "客先同行要否"].freeze

def assert_test(condition, message)
  raise "ASSERTION FAILED: #{message}" unless condition
end

def run_bootstrap(project_id:, retire:, expect_failure: false)
  ENV["REDMINE_API_KEY"] = "disposable-migration-api-key"
  ENV["REDMINE_PROJECT_ID"] = project_id.to_s
  ENV["REDMINE_PROJECT_IDENTIFIER"] = "internal-inquiry"
  ENV["REDMINE_PROJECT_NAME"] = "Internal Support"
  ENV["REDMINE_LANG"] = "en"
  ENV["ENABLE_TEST_USERS"] = "false"
  ENV["RETIRE_LEGACY_REQUEST_FIELDS"] = retire ? "true" : "false"

  load BOOTSTRAP_PATH
  raise "bootstrap unexpectedly succeeded" if expect_failure
rescue SystemExit => error
  raise unless expect_failure && !error.success?
end

def create_issue(project:, tracker:, status:, priority:, author:, subject:)
  Issue.create!(
    project: project,
    tracker: tracker,
    status: status,
    priority: priority,
    author: author,
    subject: subject,
    description: "disposable migration fixture"
  )
end

def workflow_signature(tracker, role)
  WorkflowTransition.where(tracker_id: tracker.id, role_id: role.id)
                    .order(:old_status_id, :new_status_id)
                    .pluck(:old_status_id, :new_status_id)
end

run_bootstrap(project_id: 1, retire: false)

project = Project.find_by!(identifier: "internal-inquiry")
admin = User.find_by!(login: "admin")
trackers = TRACKER_NAMES.to_h { |name| [name, Tracker.find_by!(name: name)] }
status = IssueStatus.find_by!(name: "対応待ち")
priority = IssuePriority.default || IssuePriority.first!

other_project = Project.new(
  name: "Migration isolation project",
  identifier: "migration-isolation",
  is_public: false
)
other_project.enabled_module_names = ["issue_tracking"]
other_project.trackers = [trackers.fetch("問い合わせ")]
other_project.save!

LEGACY_FIELD_NAMES.each do |name|
  field = IssueCustomField.new(
    name: name,
    field_format: "bool",
    default_value: "0",
    is_required: false,
    is_for_all: false,
    visible: true
  )
  field.projects = [project]
  field.trackers = trackers.values
  field.save!
end

target_issue = create_issue(
  project: project,
  tracker: trackers.fetch("問い合わせ"),
  status: status,
  priority: priority,
  author: admin,
  subject: "target issue must be retired"
)
other_issue = create_issue(
  project: other_project,
  tracker: trackers.fetch("問い合わせ"),
  status: status,
  priority: priority,
  author: admin,
  subject: "other project issue must survive"
)
Setting.cross_project_subtasks = "system"
other_issue.parent_issue_id = target_issue.id
other_issue.save!

legacy_question = "報告書が欲しいです"
legacy_answer = "チケットを作成（既にやりとりするチケットがある場合は更新）し、報告書が必要にチェックを入れて対応情報を更新してください"
new_answer = "報告書チケットを作成し、対応情報を更新してください"
faq_page = project.wiki.find_page("FAQ_report_request")
faq_content = faq_page.content
faq_content.text = "Q: #{legacy_question}\n\nA:\n#{legacy_answer}"
faq_content.author = admin
assert_test(faq_page.save_with_content(faq_content), "legacy FAQ fixture must save")
faq_page.reload
faq_content_id = faq_page.content.id
faq_version_before = faq_page.content.version

run_bootstrap(project_id: other_project.id, retire: true, expect_failure: true)
assert_test(Issue.exists?(target_issue.id), "project ID mismatch must not delete target issues")
assert_test(Issue.exists?(other_issue.id), "project ID mismatch must not delete other-project issues")
assert_test(
  IssueCustomField.where(name: LEGACY_FIELD_NAMES).count == 2,
  "project ID mismatch must not delete legacy fields"
)

run_bootstrap(project_id: project.id, retire: false)
assert_test(Issue.exists?(target_issue.id), "normal bootstrap must not retire target issues")
assert_test(
  IssueCustomField.where(name: LEGACY_FIELD_NAMES).count == 2,
  "normal bootstrap must not delete legacy fields"
)

faq_page.reload
assert_test(faq_page.content.id == faq_content_id, "exact-match FAQ migration must reuse WikiContent")
assert_test(faq_page.content.version == faq_version_before + 1, "FAQ migration must append one version")
assert_test(
  faq_page.content.versions.any? { |version| version.text == "Q: #{legacy_question}\n\nA:\n#{legacy_answer}" },
  "FAQ history must retain the legacy seed body"
)
assert_test(faq_page.content.text == "Q: #{legacy_question}\n\nA:\n#{new_answer}", "FAQ body must migrate")

project.reload
assert_test(project.trackers.pluck(:name).sort == TRACKER_NAMES.sort, "project tracker associations")
trackers.each_value do |tracker|
  assert_test(tracker.reload.default_status == status, "#{tracker.name} default status")
end

expected_field_trackers = {
  "顧客ID" => TRACKER_NAMES,
  "報告書渡し済み" => ["報告書"],
  "予定・担当者アサイン済み" => ["客先同行"],
  "同行方法" => ["客先同行"]
}
expected_field_trackers.each do |name, expected_trackers|
  field = IssueCustomField.find_by!(name: name)
  assert_test(field.projects.pluck(:id) == [project.id], "#{name} project association")
  assert_test(field.trackers.pluck(:name).sort == expected_trackers.sort, "#{name} tracker associations")
end

visit_mode = IssueCustomField.find_by!(name: "同行方法")
assert_test(visit_mode.field_format == "list", "visit mode field format")
assert_test(visit_mode.possible_values == ["オンライン", "オフライン"], "visit mode options")
assert_test(visit_mode.is_required?, "visit mode must be required")
assert_test(!visit_mode.multiple?, "visit mode must allow only one choice")

["営業担当者", "サポート担当者"].each do |role_name|
  role = Role.find_by!(name: role_name)
  inquiry_workflow = workflow_signature(trackers.fetch("問い合わせ"), role)
  assert_test(inquiry_workflow.any?, "#{role_name} inquiry workflow")
  ["報告書", "客先同行"].each do |tracker_name|
    assert_test(
      workflow_signature(trackers.fetch(tracker_name), role) == inquiry_workflow,
      "#{role_name} #{tracker_name} workflow must match inquiry"
    )
  end
end

run_bootstrap(project_id: project.id, retire: true, expect_failure: true)
assert_test(Issue.exists?(target_issue.id), "cross-project child guard must preserve target issues")
assert_test(Issue.exists?(other_issue.id), "cross-project child guard must preserve external children")
assert_test(
  IssueCustomField.where(name: LEGACY_FIELD_NAMES).count == 2,
  "cross-project child guard must preserve legacy fields"
)

other_issue.reload
other_issue.parent_issue_id = nil
other_issue.save!
run_bootstrap(project_id: project.id, retire: true)
assert_test(!Issue.exists?(target_issue.id), "explicit migration must delete target-project issues")
assert_test(Issue.exists?(other_issue.id), "explicit migration must preserve other-project issues")
assert_test(
  IssueCustomField.where(name: LEGACY_FIELD_NAMES).none?,
  "explicit migration must delete both legacy fields"
)

survivor = create_issue(
  project: project,
  tracker: trackers.fetch("報告書"),
  status: status,
  priority: priority,
  author: admin,
  subject: "second-run survivor"
)
run_bootstrap(project_id: project.id, retire: true)
assert_test(Issue.exists?(survivor.id), "second migration run must preserve new issues")
assert_test(Issue.exists?(other_issue.id), "second migration run must preserve isolated issues")

puts "Disposable Redmine tracker migration assertions passed"
