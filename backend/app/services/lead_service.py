"""Lead state machine (docs/DATABASE.md — transiciones válidas).

Terminal states are only re-enterable by admins; sales must follow the
transition table. Kept in a service (not the router) so tests and future
automations (M5: follow-ups on no_answer) reuse the same rules.
"""

from __future__ import annotations

from app.models.enums import LeadStatus

ALLOWED_TRANSITIONS: dict[LeadStatus, frozenset[LeadStatus]] = {
    LeadStatus.NEW: frozenset(
        {LeadStatus.QUALIFIED, LeadStatus.CONTACTED, LeadStatus.NO_RESPONSE, LeadStatus.DUPLICATE, LeadStatus.OUT_OF_AREA}
    ),
    LeadStatus.QUALIFIED: frozenset(
        {LeadStatus.CONTACTED, LeadStatus.NO_RESPONSE, LeadStatus.NOT_INTERESTED, LeadStatus.OUT_OF_AREA}
    ),
    LeadStatus.CONTACTED: frozenset(
        {
            LeadStatus.INTERESTED,
            LeadStatus.NO_RESPONSE,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.WRONG_NUMBER,
            LeadStatus.MEETING,
            LeadStatus.QUALIFIED,
            LeadStatus.OUT_OF_AREA,
            LeadStatus.DUPLICATE,
        }
    ),
    LeadStatus.NO_RESPONSE: frozenset({LeadStatus.FOLLOW_UP, LeadStatus.CONTACTED}),
    LeadStatus.FOLLOW_UP: frozenset(
        {LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.NOT_INTERESTED}
    ),
    LeadStatus.INTERESTED: frozenset(
        {LeadStatus.MEETING, LeadStatus.CUSTOMER, LeadStatus.NOT_INTERESTED}
    ),
    LeadStatus.MEETING: frozenset(
        {LeadStatus.CUSTOMER, LeadStatus.NOT_INTERESTED, LeadStatus.FOLLOW_UP}
    ),
    # Terminals: only an admin may move away from these.
    LeadStatus.CUSTOMER: frozenset(),
    LeadStatus.NOT_INTERESTED: frozenset(),
    LeadStatus.WRONG_NUMBER: frozenset(),
    LeadStatus.OUT_OF_AREA: frozenset(),
    LeadStatus.DUPLICATE: frozenset(),
}


class InvalidTransition(Exception):
    def __init__(self, current: LeadStatus, new: LeadStatus) -> None:
        self.current = current
        self.new = new
        super().__init__(f"Transición inválida: {current.value} → {new.value}")


def validate_transition(
    current: LeadStatus, new: LeadStatus, *, is_admin: bool
) -> None:
    """Raise InvalidTransition when sales tries an out-of-table move."""
    if current == new:
        return  # idempotent no-op
    if new in ALLOWED_TRANSITIONS[current]:
        return
    if not is_admin:
        raise InvalidTransition(current, new)
