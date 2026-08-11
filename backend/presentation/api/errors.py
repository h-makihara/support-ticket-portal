"""Stable public error responses."""

from fastapi.responses import JSONResponse


def internal_server_error() -> JSONResponse:
    """Hide implementation details behind the documented error contract."""
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
