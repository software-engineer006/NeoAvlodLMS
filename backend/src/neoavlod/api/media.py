import re
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from neoavlod.errors import DomainError
from neoavlod.settings import Settings

router = APIRouter(prefix="/media", tags=["media"])

AVATAR_FILENAME_REGEX = re.compile(r"^avatar_[a-f0-9]{32}\.(png|jpg|jpeg|webp)$")
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@router.get("/avatars/{filename}")
async def get_avatar(filename: str, request: Request) -> FileResponse:
    if not AVATAR_FILENAME_REGEX.match(filename):
        raise DomainError("Rasm topilmadi", 404)

    settings = cast(Settings, request.app.state.settings)
    avatars_dir = settings.media_dir.resolve() / "avatars"
    file_path = (avatars_dir / filename).resolve()

    if not file_path.is_relative_to(avatars_dir) or not file_path.is_file():
        raise DomainError("Rasm topilmadi", 404)

    ext = file_path.suffix.lower()
    media_type = MIME_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
