from cryptography.fernet import Fernet, InvalidToken

from neoavlod.errors import DomainError
from neoavlod.settings import Settings


def cipher(settings: Settings) -> Fernet:
    if settings.bot_encryption_key is None:
        if settings.environment == "test":
            return Fernet(b"dGVzdF9rZXlfdGVzdF9rZXlfdGVzdF9rZXlfdGVzdF8=")
        raise DomainError("Bot encryption kaliti sozlanmagan", 503)
    return Fernet(settings.bot_encryption_key.get_secret_value().encode())


def encrypt_token(token: str, settings: Settings) -> str:
    return cipher(settings).encrypt(token.encode()).decode()


def decrypt_token(encrypted: str, settings: Settings) -> str:
    try:
        return cipher(settings).decrypt(encrypted.encode()).decode()
    except (InvalidToken, UnicodeDecodeError):
        raise DomainError("Bot token shifrini ochib bo‘lmadi", 503) from None


encrypt_secret = encrypt_token
decrypt_secret = decrypt_token
