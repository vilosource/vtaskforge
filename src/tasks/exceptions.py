class InvalidTransition(Exception):
    def __init__(self, current_status, requested_status, valid_transitions):
        self.current_status = current_status
        self.requested_status = requested_status
        self.valid_transitions = valid_transitions
        super().__init__(
            f"Cannot transition from '{current_status}' to '{requested_status}'. "
            f"Valid transitions: {valid_transitions}"
        )


class GuardViolation(InvalidTransition):
    """A transition guard prevented the status change."""

    def __init__(self, current_status, requested_status, guard_name, message):
        self.guard_name = guard_name
        # Pass empty valid_transitions — the transition is structurally valid but
        # blocked by a business rule.
        super().__init__(current_status, requested_status, [])
        # Override the message from InvalidTransition
        self.args = (message,)
