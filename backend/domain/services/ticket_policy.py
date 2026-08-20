"""Ticket policies shared by use cases."""

ROLE_SALES = "sales"
ROLE_SUPPORT = "support"
ROLE_ADMIN = "admin"

AUTHOR_REASSIGNMENT_FIELDS = frozenset(
    {"report_delivered", "schedule_assigned"}
)
