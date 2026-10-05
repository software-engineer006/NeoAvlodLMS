import uuid
from datetime import time
from decimal import Decimal
from typing import Any

from neoavlod.models import Group, Parent, Staff, Student


def staff(**overrides: Any) -> Staff:
    suffix = uuid.uuid4()
    values: dict[str, Any] = {
        "first_name": "Ali",
        "last_name": "Valiyev",
        "phone": f"+998{suffix.int % 10**9:09d}",
        "username": f"user_{suffix.hex[:12]}",
        "hashed_password": "$argon2id$encoded-test-password",
    }
    return Staff(**(values | overrides))


def group(subject_id: uuid.UUID, teacher_id: uuid.UUID, **overrides: Any) -> Group:
    values: dict[str, Any] = {
        "name": "Matematika A",
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "monthly_price": Decimal("450000.00"),
        "max_students": 20,
        "days_of_week": [1, 3, 5],
        "start_time": time(9),
        "end_time": time(10),
        "room_number": "101",
    }
    return Group(**(values | overrides))


def parent(**overrides: Any) -> Parent:
    values = {"first_name": "Vali", "last_name": "Aliyev", "phone": "+998901234567"}
    return Parent(**(values | overrides))


def student(group_id: uuid.UUID, parent_id: uuid.UUID, **overrides: Any) -> Student:
    values: dict[str, Any] = {
        "first_name": "Anvar",
        "last_name": "Valiyev",
        "phone": "+998901112233",
        "age": 12,
        "group_id": group_id,
        "parent_id": parent_id,
    }
    return Student(**(values | overrides))
