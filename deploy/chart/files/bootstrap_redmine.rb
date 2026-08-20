# Idempotent Redmine bootstrap used by Docker Compose and Helm.

api_key = ENV.fetch("REDMINE_API_KEY")
project_identifier = ENV.fetch("REDMINE_PROJECT_IDENTIFIER", "internal-inquiry")

if Tracker.none? || IssueStatus.none? || IssuePriority.none?
  Redmine::DefaultData::Loader.load(ENV.fetch("REDMINE_LANG", "en"))
end

Setting.rest_api_enabled = "1"

admin = User.find_by!(login: "admin")
admin.update!(must_change_passwd: false)

# Reuse Redmine's default status rows where possible so existing issues keep
# their status IDs when this bootstrap is applied to an existing environment.
status_definitions = [
  ["対応待ち",   ["新規", "New"],            false],
  ["対応中",     ["In Progress"],            false],
  ["対応済",     ["回答済", "Resolved"],      false],
  ["クローズ待ち", ["Rejected"],              false],
  ["クローズ",   ["Closed"],                 true]
]
statuses = {}
status_definitions.each_with_index do |(name, legacy_names, is_closed), index|
  status = IssueStatus.find_by(name: name)
  status ||= IssueStatus.where(name: legacy_names).order(:id).first
  status ||= IssueStatus.new
  status.name = name
  status.is_closed = is_closed
  status.position = index + 1
  status.save!
  statuses[name] = status
end

# 「追加質問」は「対応待ち」へ統合する。既存チケットを移行し、参照する
# ワークフローを消してから旧ステータス自体を削除する。
obsolete_statuses = IssueStatus.where(
  name: ["追加質問", "Feedback", "Reopened"]
).where.not(id: statuses.fetch("対応待ち").id)
obsolete_statuses.each do |obsolete_status|
  Issue.where(status_id: obsolete_status.id).update_all(
    status_id: statuses.fetch("対応待ち").id
  )
  Tracker.where(default_status_id: obsolete_status.id).update_all(
    default_status_id: statuses.fetch("対応待ち").id
  )
  WorkflowTransition.where(old_status_id: obsolete_status.id).delete_all
  WorkflowTransition.where(new_status_id: obsolete_status.id).delete_all
  obsolete_status.destroy!
end

# Trackers, roles and workflows are administration resources and cannot be
# created through Redmine's REST API. Provision them from inside Redmine.
tracker_names = ["問い合わせ", "報告書", "客先同行"]
trackers = tracker_names.to_h do |name|
  tracker = Tracker.find_or_initialize_by(name: name)
  tracker.default_status = statuses.fetch("対応待ち")
  tracker.save!
  [name, tracker]
end

role_permissions = {
  "営業担当者" => [:view_issues, :add_issues, :edit_issues, :add_issue_notes, :view_wiki_pages],
  "サポート担当者" => [
    :view_issues, :add_issues, :edit_issues, :add_issue_notes,
    :view_wiki_pages, :edit_wiki_pages, :delete_wiki_pages
  ]
}
roles = {}
role_permissions.each do |name, permissions|
  role = Role.find_or_initialize_by(name: name)
  role.permissions = permissions
  role.issues_visibility = "all"
  role.save!
  roles[name] = role
end

Token.where(user: admin, action: "api").delete_all
token = Token.create!(user: admin, action: "api")
# Token generates its own value on create; Compose needs a stable shared key.
token.update_column(:value, api_key)

project = Project.find_or_initialize_by(identifier: project_identifier)
project.name = ENV.fetch("REDMINE_PROJECT_NAME", "Internal Support")
project.description = "Support ticket portal project"
project.is_public = false
project.enabled_module_names = (project.enabled_module_names + ["issue_tracking", "wiki"]).uniq
project.trackers = trackers.values
project.save!

legacy_fields = IssueCustomField.where(name: ["報告書要否", "客先同行要否"])
if legacy_fields.any? { |field| field.projects.exists?(project.id) }
  ActiveRecord::Base.transaction do
    project.issues.find_each(&:destroy!)
    legacy_fields.each(&:destroy!)
  end
end

wiki = project.wiki || Wiki.new(project: project)
wiki.start_page = "FAQ"
wiki.save!

sample_faqs = {
  "FAQ_report_request" => [
    "報告書が欲しいです",
    "チケットを作成（既にやりとりするチケットがある場合は更新）し、報告書が必要にチェックを入れて対応情報を更新してください",
    "報告書チケットを作成し、対応情報を更新してください"
  ],
  "FAQ_customer_visit" => [
    "報告書がわかりにくいので一緒に客先に同行してほしいです",
    "チケットを作成（既にやりとりするチケットがある場合は更新）し、客先同行が必要にチェックを入れて対応情報を更新してください",
    "客先同行チケットを作成し、対応情報を更新してください"
  ]
}
sample_faqs.each do |title, (question, legacy_answer, answer)|
  content_text = "Q: #{question}\n\nA:\n#{answer}"
  page = wiki.find_page(title)
  next if page && page.content&.text != "Q: #{question}\n\nA:\n#{legacy_answer}"

  page ||= WikiPage.new(wiki: wiki, title: title)
  content = WikiContent.new(
    page: page,
    author: admin,
    text: content_text
  )
  page.save_with_content(content) || abort("Failed to create sample FAQ #{title}: #{page.errors.full_messages.join(', ')}")
end

# Portal-specific issue fields. Boolean defaults are explicitly false so both
# newly created and existing issues have a predictable value in the portal.
custom_field_definitions = [
  ["顧客ID", "string", "", false, tracker_names],
  ["報告書渡し済み", "bool", "0", true, ["報告書"]],
  ["予定・担当者アサイン済み", "bool", "0", true, ["客先同行"]]
]
custom_field_definitions.each do |name, format, default_value, support_only, field_tracker_names|
  custom_field = IssueCustomField.find_or_initialize_by(name: name)
  custom_field.field_format = format
  custom_field.default_value = default_value
  custom_field.is_required = false
  custom_field.is_for_all = false
  custom_field.trackers = field_tracker_names.map { |name| trackers.fetch(name) }
  custom_field.projects = [project]
  # Redmine interprets visible=false plus role_ids as visibility restricted to
  # those roles. The portal API also enforces this boundary independently.
  custom_field.visible = !support_only
  custom_field.role_ids = support_only ? [roles.fetch("サポート担当者").id] : []
  custom_field.save!
end

# 対応待ち → 対応中 → 対応済 → 対応待ち（再質問・追加質問）
#                         └→ クローズ待ち → クローズ
workflow_edges = [
  [nil, "対応待ち"],
  ["対応待ち", "対応中"],
  ["対応待ち", "対応済"],
  ["対応中", "対応待ち"],
  ["対応中", "対応済"],
  ["対応済", "対応待ち"],
  ["対応済", "クローズ待ち"],
  ["クローズ待ち", "対応待ち"],
  ["クローズ待ち", "対応済"],
  ["クローズ待ち", "クローズ"]
]
sales_destinations = ["対応待ち", "クローズ待ち", "クローズ"]

workflow_trackers = trackers.values
roles.each do |role_name, role|
  workflow_trackers.each do |workflow_tracker|
    WorkflowTransition.where(
      tracker_id: workflow_tracker.id,
      role_id: role.id
    ).delete_all
    workflow_edges.each do |old_name, new_name|
      next if role_name == "営業担当者" &&
              old_name &&
              !sales_destinations.include?(new_name)

      WorkflowTransition.create!(
        tracker_id: workflow_tracker.id,
        role_id: role.id,
        old_status_id: old_name ? statuses.fetch(old_name).id : 0,
        new_status_id: statuses.fetch(new_name).id
      )
    end
  end
end

unless project.id == Integer(ENV.fetch("REDMINE_PROJECT_ID", "1"))
  abort "Expected project ID #{ENV.fetch('REDMINE_PROJECT_ID', '1')}, got #{project.id}"
end

if ENV.fetch("ENABLE_TEST_USERS", "false") == "true"
  users = {
    admin: ["TEST_ADMIN", nil],
    support: ["TEST_SUPPORT", roles.fetch("サポート担当者")],
    sales: ["TEST_SALES", roles.fetch("営業担当者")]
  }
  users.each_value do |prefix, role|
    login = ENV.fetch("#{prefix}_USERNAME")
    password = ENV.fetch("#{prefix}_PASSWORD")
    email = ENV.fetch("#{prefix}_EMAIL")
    user = User.find_or_initialize_by(login: login)
    user.firstname = prefix.split("_").last.capitalize
    user.lastname = "Tester"
    user.mail = email
    user.password = password
    user.password_confirmation = password
    user.status = User::STATUS_ACTIVE
    # Keep API login usable for automated verification; rotate these local-only
    # credentials after delivery if the environment will be retained.
    user.must_change_passwd = false
    user.admin = role.nil?
    user.save!
    Member.find_or_create_by!(project: project, user: user) { |member| member.roles = [role] } if role
  end
end

puts "Redmine bootstrap complete (project_id=#{project.id})"
