class DomainError(Exception):
    """A public, intentional error message without database or secret details."""

    def __init__(self, message: str, status_code: int = 400, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


TELEGRAM_NOT_LINKED = "telegram_not_linked"


def telegram_not_linked() -> DomainError:
    return DomainError(
        "Telegram botga hali ulanmagan. Administratordan bot havolasini oling "
        "va botda /start tugmasini bosing.",
        403,
        TELEGRAM_NOT_LINKED,
    )
