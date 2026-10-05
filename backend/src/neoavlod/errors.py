class DomainError(Exception):
    """A public, intentional error message without database or secret details."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
