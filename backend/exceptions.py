class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} {identifier!r} not found")


class ConflictError(Exception):
    """Raised when a resource already exists (e.g. duplicate watch)."""

    def __init__(self, resource: str, reason: str) -> None:
        self.resource = resource
        self.reason = reason
        super().__init__(f"{resource} conflict: {reason}")
