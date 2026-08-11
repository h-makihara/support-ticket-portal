"""Ticket policies shared by use cases."""

ROLE_SALES = "sales"
ROLE_SUPPORT = "support"
ROLE_ADMIN = "admin"

PRIORITY_ESCALATION_FIELDS = frozenset(
    {"report_required", "customer_visit_required"}
)
AUTHOR_REASSIGNMENT_FIELDS = frozenset(
    {"report_delivered", "schedule_assigned"}
)


class UnknownPriorityError(ValueError):
    pass


def next_priority_id(current_priority_id: int, priority_ids: list[int]) -> int:
    """Advance one configured level and cap the result at the highest level."""
    try:
        current_index = priority_ids.index(int(current_priority_id))
    except ValueError as exc:
        raise UnknownPriorityError(current_priority_id) from exc
    return priority_ids[min(current_index + 1, len(priority_ids) - 1)]
