import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_hasher = PasswordHasher(
    time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID
)


def validate_password(password: str) -> None:
    if not 12 <= len(password) <= 128 or len(set(password)) < 4 or not password.strip():
        raise ValueError("Parol 12–128 belgi va kamida 4 xil belgidan iborat bo‘lishi kerak")


def generate_temporary_password(length: int = 14) -> str:
    """Generate a cryptographically secure password meeting policy."""
    if length < 12:
        length = 12
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*-_"

    chosen = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    all_chars = uppercase + lowercase + digits + symbols
    for _ in range(length - len(chosen)):
        chosen.append(secrets.choice(all_chars))

    shuffled = "".join(secrets.SystemRandom().sample(chosen, len(chosen)))
    validate_password(shuffled)
    return shuffled


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    if len(password) > 128:
        return False
    try:
        return _hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(encoded: str) -> bool:
    try:
        return _hasher.check_needs_rehash(encoded)
    except InvalidHashError:
        return True
