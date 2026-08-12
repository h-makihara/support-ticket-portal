#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "yaml"

ROOT = File.expand_path("../..", __dir__)
SECRETS = %w[
  secrets.redmineApiKey=x
  secrets.redmineSecretKeyBase=x
  secrets.postgresPassword=x
  secrets.testAdminPassword=x
  secrets.testSupportPassword=x
  secrets.testSalesPassword=x
].freeze

def resource(documents, kind, name)
  documents.fetch([kind, name])
end

def selector(documents, kind, name)
  resource(documents, kind, name).fetch("spec").fetch("selector")
end

def deployment_image(documents, name, container)
  containers = resource(documents, "Deployment", name)
    .dig("spec", "template", "spec", "containers")
  containers.find { |item| item.fetch("name") == container }.fetch("image")
end

def render(overrides)
  command = ["helm", "template", "support-ticket-portal", "deploy/chart"]
  (SECRETS + overrides).each { |value| command.concat(["--set", value]) }
  output, status = Open3.capture2e(*command, chdir: ROOT)
  [output, status]
end

def documents_for(overrides)
  output, status = render(overrides)
  raise "helm template failed:\n#{output}" unless status.success?

  YAML.load_stream(output).compact.to_h do |document|
    [[document.fetch("kind"), document.fetch("metadata").fetch("name")], document]
  end
end

def assert_invalid_render(overrides, message)
  output, status = render(overrides)
  raise "invalid render unexpectedly succeeded" if status.success?
  raise "missing validation message #{message.inspect}:\n#{output}" unless output.include?(message)
end

def assert_negative_renders
  assert_invalid_render(["blueGreen.activeSlot=red"], "blueGreen.activeSlot must be either blue or green")
  assert_invalid_render(["blueGreen.slots.green=null"], "blueGreen.slots.green is required")
  assert_invalid_render(["blueGreen.phase=unknown"], "blueGreen.phase must be migration, coexist, or active")
end

def assert_active
  docs = documents_for([
    "blueGreen.phase=active",
    "blueGreen.activeSlot=green",
    "blueGreen.slots.blue.backendTag=backend-blue-test",
    "blueGreen.slots.blue.frontendTag=frontend-blue-test",
    "blueGreen.slots.green.backendTag=backend-green-test",
    "blueGreen.slots.green.frontendTag=frontend-green-test"
  ])

  raise "frontend must select green" unless selector(docs, "Service", "frontend")["app.kubernetes.io/slot"] == "green"
  raise "backend must select green" unless selector(docs, "Service", "backend")["app.kubernetes.io/slot"] == "green"
  %w[blue green].each do |slot|
    raise "backend slot selector" unless selector(docs, "Service", "backend-#{slot}")["app.kubernetes.io/slot"] == slot
    raise "frontend slot selector" unless selector(docs, "Service", "frontend-#{slot}")["app.kubernetes.io/slot"] == slot
  end
  raise "active must not render legacy backend" if docs.key?(["Deployment", "backend"])
  raise "active must not render legacy frontend" if docs.key?(["Deployment", "frontend"])
  raise "wrong blue backend image" unless deployment_image(docs, "backend-blue", "backend").end_with?(":backend-blue-test")
  raise "wrong green frontend image" unless deployment_image(docs, "frontend-green", "frontend").end_with?(":frontend-green-test")
  raise "blue frontend routes to wrong backend" unless resource(docs, "ConfigMap", "frontend-blue-nginx").fetch("data").fetch("default.conf").include?("proxy_pass http://backend-blue:8000/;")
  raise "green frontend routes to wrong backend" unless resource(docs, "ConfigMap", "frontend-green-nginx").fetch("data").fetch("default.conf").include?("proxy_pass http://backend-green:8000/;")
  raise "slot frontend must mount its Nginx ConfigMap" unless resource(docs, "Deployment", "frontend-green").dig("spec", "template", "spec", "volumes").any? { |volume| volume.dig("configMap", "name") == "frontend-green-nginx" }

  assert_negative_renders
end

def assert_migration
  docs = documents_for(["blueGreen.phase=migration"])
  raise unless resource(docs, "Deployment", "backend").dig("spec", "selector", "matchLabels").keys.sort == ["app.kubernetes.io/instance", "app.kubernetes.io/name"]
  raise unless resource(docs, "Deployment", "backend").dig("spec", "template", "metadata", "labels", "app.kubernetes.io/slot") == "blue"
  raise if selector(docs, "Service", "backend").key?("app.kubernetes.io/slot")
  raise if selector(docs, "Service", "frontend").key?("app.kubernetes.io/slot")
  raise if docs.key?(["Deployment", "backend-blue"])
  raise if docs.key?(["ConfigMap", "frontend-blue-nginx"])

  assert_negative_renders
end

def assert_coexist
  docs = documents_for(["blueGreen.phase=coexist"])
  %w[backend frontend].each do |name|
    raise "missing legacy #{name}" unless docs.key?(["Deployment", name])
    %w[blue green].each do |slot|
      raise "missing #{name}-#{slot}" unless docs.key?(["Deployment", "#{name}-#{slot}"])
      raise "missing #{name}-#{slot} Service" unless docs.key?(["Service", "#{name}-#{slot}"])
    end
    raise "stable #{name} must select blue" unless selector(docs, "Service", name)["app.kubernetes.io/slot"] == "blue"
  end

  assert_negative_renders
end

case ARGV.fetch(0)
when "active" then assert_active
when "migration" then assert_migration
when "coexist" then assert_coexist
else abort "usage: #{$PROGRAM_NAME} [active|migration|coexist]"
end
