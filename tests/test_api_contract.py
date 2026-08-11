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
