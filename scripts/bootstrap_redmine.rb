# Idempotent Redmine bootstrap used by Docker Compose.

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
  ["新規",       ["New"],                    false],
  ["対応中",     ["In Progress"],            false],
  ["回答済",     ["Resolved"],               false],
  ["追加質問",   ["Feedback", "Reopened"],   false],
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

# Trackers, roles and workflows are administration resources and cannot be
# created through Redmine's REST API. Provision them from inside Redmine.
tracker_name = ENV.fetch("REDMINE_TRACKER_NAME", "問い合わせ")
tracker = Tracker.find_or_initialize_by(name: tracker_name)
tracker.default_status = statuses.fetch("新規")
tracker.save!

role_permissions = {
  "営業担当者" => [:view_issues, :add_issues, :edit_issues, :add_issue_notes],
  "サポート担当者" => [:view_issues, :add_issues, :edit_issues, :add_issue_notes]
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
project.enabled_module_names = (project.enabled_module_names + ["issue_tracking"]).uniq
project.trackers = Tracker.all.to_a
project.save!

# Most complex route:
# 新規 → 対応中 → 回答済 → 追加質問 → 対応中 → 回答済
#      → クローズ待ち → クローズ
workflow_edges = [
  [nil, "新規"],
  ["新規", "対応中"],
  ["対応中", "回答済"],
  ["回答済", "追加質問"],
  ["追加質問", "対応中"],
  ["回答済", "クローズ待ち"],
  ["クローズ待ち", "クローズ"]
]
sales_destinations = ["回答済", "追加質問", "クローズ待ち"]

workflow_trackers = (project.trackers.to_a + [tracker]).uniq
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
