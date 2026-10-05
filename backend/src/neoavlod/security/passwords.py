from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_hasher = PasswordHasher(
    time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID
)


def validate_password(password: str) -> None:
    if not 12 <= len(password) <= 128 or len(set(password)) < 4 or not password.strip():
        raise ValueError("Parol 12–128 belgi va kamida 4 xil belgidan iborat bo‘lishi kerak")


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
