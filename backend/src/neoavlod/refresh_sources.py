"""Strict read-only planning for the reviewed seven-file educenter refresh."""

import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from neoavlod.roster_import import normalized, parse_phone, parse_times

FILES = (
    "English Elementry&Beginer 1-gruh.csv",
    "English Pre-intermediate 2-gruh.csv",
    "English Elementry&Beginer 3-gruh.csv",
    *(f"Python&vibecoding {n}-gruh.csv" for n in range(1, 5)),
)
DAY_NAMES = {
    "dushanba": 1,
    "seshanba": 2,
    "chorshanba": 3,
    "payshanba": 4,
    "juma": 5,
    "shanba": 6,
    "yakshanba": 7,
}
LESSON = re.compile(r"(?:Sentyabr: |Oktyabr: )?\d+-dars \((\d+)-(sentyabr|oktyabr)\)", re.I)


@dataclass(frozen=True)
class SourceRow:
    file: str
    row: int
    cells: list[str]


@dataclass
class RefreshPerson:
    key: str
    full_name: str
    phone: str | None
    phone_candidates: list[str]
    school_grade: str | None
    school_name: str | None
    review_fields: list[str]
    sources: list[SourceRow]


@dataclass
class RefreshEnrollment:
    person_key: str
    group_name: str
    level: str | None
    mygov_status: str | None
    notes: str | None
    present_dates: list[str]
    sources: list[SourceRow]


@dataclass
class RefreshGroup:
    file: str
    name: str
    teacher_name: str
    subject_name: str
    days: list[int]
    start_time: str
    end_time: str
    room_number: str | None
    source_times: list[str]
    lesson_dates: list[str]


@dataclass
class RefreshManifest:
    year: int
    files: dict[str, str] = field(default_factory=dict)
    headers: dict[str, list[str]] = field(default_factory=dict)
    groups: list[RefreshGroup] = field(default_factory=list)
    people: list[RefreshPerson] = field(default_factory=list)
    enrollments: list[RefreshEnrollment] = field(default_factory=list)

    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(raw).hexdigest()

    def summary(self) -> dict[str, int]:
        return {
            "files": len(self.files),
            "groups": len(self.groups),
            "profiles": len(self.people),
            "memberships": len(self.enrollments),
            "source_rows": sum(len(e.sources) for e in self.enrollments),
            "present_drafts": sum(len(e.present_dates) for e in self.enrollments),
            "absent_inferred": 0,
            "profiles_to_review": sum(bool(p.review_fields) for p in self.people),
        }


def _identity(value: str) -> str:
    return normalized(value.replace("ʻ", "'"))


def _consensus(values: list[str]) -> str | None:
    unique = {value for value in values if value}
    return next(iter(unique)) if len(unique) == 1 else None


def _joined(values: list[str]) -> str | None:
    return " / ".join(dict.fromkeys(v for v in values if v)) or None


def _time_pair(value: str) -> tuple[str, str]:
    start, end = parse_times(value)
    if start is None or end is None:
        raise ValueError("Dars vaqti to‘liq va aniq bo‘lishi kerak")
    return start.strftime("%H:%M"), end.strftime("%H:%M")


def _days(value: str) -> list[int]:
    words = re.split(r"[,\s]+", value.strip().casefold())
    words = [word for word in words if word and word != "va"]
    if not words or any(word not in DAY_NAMES for word in words):
        raise ValueError("Dars kunlari tekshirilishi kerak")
    return sorted({DAY_NAMES[word] for word in words})


def build_refresh_manifest(
    source: Path,
    *,
    year: int,
    time_overrides: Mapping[str, tuple[str, str]] | None = None,
) -> RefreshManifest:
    if not 1 <= year <= 9999 or {p.name for p in source.glob("*.csv")} != set(FILES):
        raise ValueError("Yil yoki yettita CSV fayl to‘plami mos emas")
    overrides = time_overrides or {}
    if set(overrides) - {Path(name).stem for name in FILES}:
        raise ValueError("Noma’lum guruh uchun vaqt tuzatishi berilgan")
    manifest = RefreshManifest(year)
    persons: dict[str, list[tuple[SourceRow, dict[str, str]]]] = defaultdict(list)
    for filename in FILES:
        raw = (source / filename).read_bytes()
        manifest.files[filename] = hashlib.sha256(raw).hexdigest()
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
        if len(rows) < 3:
            raise ValueError(f"CSV qatorlari yetarli emas: {filename}")
        header, footer = rows[0], rows[-1]
        english = filename.startswith("English")
        base = ["T/r", "Guruh nomi", "Teacher", "Ism va familiya", "Telefon raqam", "Sinf"]
        if english:
            base.append("Darajasi")
        base += ["Dars kuni", "Dars vaqti", "Maktabi", "MyGov statusi"]
        if header[: len(base)] != base or header[-2:] != ['Jami kelgan ("k")', "Izoh"]:
            raise ValueError(f"CSV sarlavhasi tekshirilishi kerak: {filename}")
        manifest.headers[filename] = header
        lessons: dict[int, str] = {}
        for index in range(len(base), len(header) - 2):
            match = LESSON.fullmatch(header[index])
            if match is None:
                raise ValueError(f"Dars sanasi aniq emas: {filename}, ustun {index + 1}")
            month = 9 if match[2].casefold() == "sentyabr" else 10
            lessons[index] = date(year, month, int(match[1])).isoformat()
        if not lessons or len(set(lessons.values())) != len(lessons):
            raise ValueError(f"Takroriy yoki bo‘sh dars sanalari: {filename}")
        group_name = Path(filename).stem
        by_person: dict[str, list[tuple[SourceRow, dict[str, str], list[str]]]] = defaultdict(list)
        counts: dict[int, int] = defaultdict(int)
        metadata: list[dict[str, str]] = []
        for row_number, row in enumerate(rows[1:-1], 2):
            if len(row) != len(header) or not row[0].isdigit() or int(row[0]) != row_number - 1:
                raise ValueError(f"CSV qator tuzilishi mos emas: {filename}, qator {row_number}")
            values = dict(zip(header, (v.strip() for v in row), strict=True))
            name = " ".join(values["Ism va familiya"].split())
            limits = {
                "Ism va familiya": 201,
                "Teacher": 201,
                "Sinf": 100,
                "Maktabi": 150,
                "MyGov statusi": 150,
                "Izoh": 2000,
            }
            if len(name.split()) < 2 or values["Guruh nomi"] != group_name:
                raise ValueError(
                    f"Ism yoki guruh tuzilishi mos emas: {filename}, qator {row_number}"
                )
            if not values["Teacher"] or any(
                len(values[key]) > limit for key, limit in limits.items()
            ):
                raise ValueError(f"Ma’lumot uzunligi mos emas: {filename}, qator {row_number}")
            present: list[str] = []
            for col, day in lessons.items():
                token = row[col].strip().casefold()
                if token not in ("", "k"):
                    raise ValueError(f"Davomat belgisi noaniq: {filename}, qator {row_number}")
                if token == "k":
                    present.append(day)
                    counts[col] += 1
            if values['Jami kelgan ("k")'] != str(len(present)):
                raise ValueError(f"Qator davomat jami mos emas: {filename}, qator {row_number}")
            entry = SourceRow(filename, row_number, row)
            key = _identity(name)
            by_person[key].append((entry, values, present))
            persons[key].append((entry, values))
            metadata.append(values)
        if len(footer) != len(header) or not footer[0].startswith("Jami qatnashganlar"):
            raise ValueError(f"Yakuniy jami qatori mos emas: {filename}")
        if any(footer[col].strip() != str(counts[col]) for col in lessons) or (
            footer[-2].strip() != str(sum(counts.values()))
        ):
            raise ValueError(f"Guruh davomat jami mos emas: {filename}")
        if not metadata:
            raise ValueError(f"Guruhda o‘quvchi yo‘q: {filename}")
        teacher_name = _consensus([v["Teacher"] for v in metadata])
        days = {_days_key(v["Dars kuni"]) for v in metadata}
        times = {_time_pair(v["Dars vaqti"]) for v in metadata}
        if (
            teacher_name is None
            or len(days) != 1
            or (len(times) != 1 and group_name not in overrides)
        ):
            raise ValueError(f"Ustoz yoki jadval bo‘yicha tasdiq kerak: {filename}")
        start, end = overrides.get(group_name, sorted(times)[0])
        start, end = _time_pair(f"{start}-{end}")
        manifest.groups.append(
            RefreshGroup(
                filename,
                group_name,
                teacher_name,
                "Ingliz tili" if english else "Python&vibecoding",
                list(next(iter(days))),
                start,
                end,
                None if english else "217",
                sorted({v["Dars vaqti"] for v in metadata}),
                list(lessons.values()),
            )
        )
        for key, entries in sorted(by_person.items()):
            values_list = [v for _, v, _ in entries]
            manifest.enrollments.append(
                RefreshEnrollment(
                    hashlib.sha256(key.encode()).hexdigest(),
                    group_name,
                    _joined([v.get("Darajasi", "") for v in values_list]),
                    _joined([v["MyGov statusi"] for v in values_list]),
                    "\n".join(dict.fromkeys(v["Izoh"] for v in values_list if v["Izoh"])) or None,
                    sorted({day for _, _, marked in entries for day in marked}),
                    [entry for entry, _, _ in entries],
                )
            )
    for key, person_entries in sorted(persons.items()):
        values_list = [values for _, values in person_entries]
        phones = sorted({phone for v in values_list if (phone := parse_phone(v["Telefon raqam"]))})
        grades = [v["Sinf"] for v in values_list]
        schools = [v["Maktabi"] for v in values_list]
        review = [
            label
            for label, values in (
                ("phone", phones),
                ("school_grade", grades),
                ("school_name", schools),
            )
            if len({v for v in values if v}) > 1
        ]
        if any(v["Telefon raqam"] and parse_phone(v["Telefon raqam"]) is None for v in values_list):
            review.append("invalid_source_phone")
        manifest.people.append(
            RefreshPerson(
                hashlib.sha256(key.encode()).hexdigest(),
                values_list[0]["Ism va familiya"],
                phones[0] if len(phones) == 1 else None,
                phones,
                _consensus(grades),
                _consensus(schools),
                review,
                [entry for entry, _ in person_entries],
            )
        )
    return manifest


def _days_key(value: str) -> tuple[int, ...]:
    return tuple(_days(value))
