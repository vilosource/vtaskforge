class InvalidTransition(Exception):
    def __init__(self, current_status, requested_status, valid_transitions):
        self.current_status = current_status
        self.requested_status = requested_status
        self.valid_transitions = valid_transitions
        super().__init__(
            f"Cannot transition from '{current_status}' to '{requested_status}'. "
            f"Valid transitions: {valid_transitions}"
        )
