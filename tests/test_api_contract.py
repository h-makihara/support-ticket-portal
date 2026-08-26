"""Regression tests for the public INPUT/OUTPUT contract."""

from backend.app import app


def test_every_operation_declares_a_success_response_schema():
    openapi = app.openapi()
    for path, operations in openapi["paths"].items():
        for method, operation in operations.items():
            if method == "parameters":
                continue
            success = next(
                response
                for status, response in operation["responses"].items()
                if status.startswith("2")
            )
            assert "schema" in success["content"]["application/json"], (method, path)


def test_login_input_marks_password_as_write_only():
    schema = app.openapi()["components"]["schemas"]["LoginInput"]
    assert schema["properties"]["password"]["writeOnly"] is True


def test_session_output_cannot_expose_redmine_credentials():
    schemas = app.openapi()["components"]["schemas"]
    serialized = str(schemas["AuthSessionOutput"])
    assert "redmine_api_key" not in serialized
    assert "password" not in serialized


def test_ticket_contract_uses_tracker_keys_and_matching_completion_fields():
    schemas = app.openapi()["components"]["schemas"]
    create = schemas["CreateTicketInput"]
    output = schemas["TicketOutput"]
    update = schemas["UpdateCustomFieldsInput"]

    assert create["additionalProperties"] is False
    assert update["additionalProperties"] is False
    assert "tracker" in create["required"]
    assert create["properties"]["tracker"]["enum"] == [
        "inquiry",
        "report",
        "customer_visit",
    ]
    assert set(create["properties"]) == {
        "tracker", "subject", "description", "priority", "customer_id",
        "report_delivered", "schedule_assigned", "visit_mode",
        "preferred_start_at_1", "preferred_start_at_2", "meeting_duration_minutes",
    }
    assert {"tracker", "tracker_name"} <= set(output["required"])
    assert set(output["properties"]) == {
        "id", "tracker", "tracker_name", "subject", "description", "status",
        "priority", "priority_name", "assignee", "latest_support_responder",
        "created_on", "updated_on", "notes", "audit_log", "customer_id",
        "report_delivered", "schedule_assigned", "visit_mode",
        "preferred_start_at_1", "preferred_start_at_2", "meeting_duration_minutes",
    }
    assert set(update["properties"]) == {
        "customer_id", "report_delivered", "schedule_assigned", "visit_mode",
        "preferred_start_at_1", "preferred_start_at_2", "meeting_duration_minutes",
    }
