import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.attendance_messages import FIELDS, PREVIEW_VALUES, render_template, validate_template
from neoavlod.models import Staff
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services.attendance_template import current_template, save_template

router = APIRouter(prefix="/api/v1/admin/attendance/message-template", tags=["attendance-template"])
TemplateEditor = Annotated[Identity, Depends(require_permission(Permission.ATTENDANCE_WRITE))]


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=3000)


class TemplateSave(TemplateIn):
    expected_version: int = Field(ge=0)


class TemplateOut(BaseModel):
    body: str
    version: int
    placeholders: list[str]
    preview: str
    updated_at: datetime | None
    changed_by: uuid.UUID | None
    editor_name: str | None


async def response(session: SessionDependency) -> TemplateOut:
    body, version, current = await current_template(session)
    editor = await session.get(Staff, current.changed_by) if current else None
    return TemplateOut(
        body=body,
        version=version,
        placeholders=sorted(FIELDS),
        preview=render_template(body, PREVIEW_VALUES),
        updated_at=current.updated_at if current else None,
        changed_by=current.changed_by if current else None,
        editor_name=f"{editor.first_name} {editor.last_name or ''}".strip() if editor else None,
    )


@router.get("", response_model=TemplateOut)
async def get_template(_: TemplateEditor, session: SessionDependency) -> TemplateOut:
    return await response(session)


@router.post("/preview")
async def preview_template(body: TemplateIn, _: TemplateEditor) -> dict[str, str]:
    return {"message": render_template(validate_template(body.body), PREVIEW_VALUES)}


@router.put("", response_model=TemplateOut)
async def update_template(
    body: TemplateSave, identity: TemplateEditor, session: SessionDependency
) -> TemplateOut:
    await save_template(session, identity.staff.id, body.body, body.expected_version)
    return await response(session)
