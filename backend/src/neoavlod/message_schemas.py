"""Validated audience and message draft shared by preview and enqueue."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MessageAudience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["selected", "groups", "all"]
    kind: Literal["parents", "students", "both"]
    group_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    parent_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_selection(self) -> "MessageAudience":
        for values in (self.group_ids, self.parent_ids, self.student_ids):
            if len(values) != len(set(values)):
                raise ValueError("Qabul qiluvchilar takrorlanmasligi kerak")
            values.sort(key=str)
        if self.scope == "groups":
            if not self.group_ids or self.parent_ids or self.student_ids:
                raise ValueError("Guruhlarni tanlang; shaxsiy ro‘yxat qo‘shilmaydi")
        elif self.scope == "all":
            if self.group_ids or self.parent_ids or self.student_ids:
                raise ValueError("Barchaga yuborishda qo‘shimcha ro‘yxat bo‘lmaydi")
        elif (not self.parent_ids and not self.student_ids) or self.group_ids:
            raise ValueError("Kamida bitta qabul qiluvchi tanlang")
        if (self.kind == "parents" and self.student_ids) or (
            self.kind == "students" and self.parent_ids
        ):
            raise ValueError("Tanlanganlar qabul qiluvchi turiga mos emas")
        return self


def format_message(title: str, body: str) -> str:
    return f"NeoAvlod LMS\n\n{title}\n\n{body}"


class MessageDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4096)
    audience: MessageAudience

    @model_validator(mode="after")
    def validate_text(self) -> "MessageDraft":
        if "\x00" in self.title + self.body:
            raise ValueError("Xabarda noto‘g‘ri belgi bor")
        try:
            length = len(format_message(self.title, self.body).encode("utf-16-le")) // 2
        except UnicodeError:
            raise ValueError("Xabarda noto‘g‘ri Unicode belgi bor") from None
        if length > 4096:
            raise ValueError("Telegram xabari sarlavha bilan 4096 belgidan oshmasligi kerak")
        return self


class MessageSend(MessageDraft):
    request_id: uuid.UUID
    preview_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
