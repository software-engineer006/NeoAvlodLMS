"""Bounded plain-text attendance templates with an exact placeholder allowlist."""

from collections.abc import Mapping
from string import Formatter

from neoavlod.errors import DomainError

DEFAULT_TEMPLATE = """NeoAvlod — Davomat bildirishnomasi

Farzandingiz: {student_name}
Fan: {subject_name}
Guruh: {group_name}
Dars sanasi: {date}
Dars vaqti: {lesson_time} (Toshkent vaqti)
Holati: {status_label}
{feedback}

NeoAvlod o‘quv markazi"""
FIELDS = frozenset(
    {
        "student_name",
        "subject_name",
        "group_name",
        "date",
        "lesson_time",
        "status_label",
        "feedback",
        "feedback_author",
    }
)
REQUIRED = frozenset(
    {"student_name", "group_name", "date", "lesson_time", "status_label", "feedback"}
)
MAX_VALUES = {
    "student_name": "𐐀" * 201,
    "subject_name": "𐐀" * 100,
    "group_name": "𐐀" * 150,
    "date": "14.10.2026",
    "lesson_time": "Kiritilmagan–Kiritilmagan",
    "status_label": "Kech qoldi",
    "feedback": "a" * 2240,
    "feedback_author": "a" * 230,
}
PREVIEW_VALUES = {
    "student_name": "Namuna O‘quvchi",
    "subject_name": "English",
    "group_name": "English A",
    "date": "14.10.2026",
    "lesson_time": "09:00–10:30",
    "status_label": "Keldi",
    "feedback": "Izoh (O‘qituvchi Namuna Ustoz): Darsda faol qatnashdi.",
    "feedback_author": "O‘qituvchi Namuna Ustoz",
}


def validate_template(body: str) -> str:
    body = body.strip()
    if not 1 <= len(body) <= 3000:
        raise DomainError("Shablon 1–3000 belgi bo‘lishi kerak", 422)
    found = set()
    try:
        for _, field, spec, conversion in Formatter().parse(body):
            if field is None:
                continue
            if field not in FIELDS or spec or conversion:
                raise ValueError
            found.add(field)
        if not REQUIRED.issubset(found):
            raise DomainError(
                "Shablonda bola, guruh, sana, vaqt, holat va feedback belgilari bo‘lishi shart", 422
            )
        if len(body.format_map(MAX_VALUES).encode("utf-16-le")) // 2 > 4070:
            raise DomainError("Shablon va maksimal izoh Telegram xabari limitidan oshadi", 422)
    except (ValueError, KeyError):
        raise DomainError(
            "Shablon belgisi yaroqsiz; faqat ko‘rsatilgan belgilarni ishlating", 422
        ) from None
    return body


def render_template(body: str, values: Mapping[str, str]) -> str:
    body = validate_template(body)
    try:
        message = body.format_map(values).strip()
    except (KeyError, ValueError):
        raise DomainError("Davomat xabari ma’lumoti yetarli emas", 422) from None
    if len(message.encode("utf-16-le")) // 2 > 4096:
        raise DomainError("Davomat xabari Telegram limitidan oshadi", 422)
    return message
