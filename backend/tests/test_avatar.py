import pytest
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import Role, Staff
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\x30\x01\x00\x9d\x01\x2a\x01\x00\x01\x00"


async def test_avatar_upload_replace_delete_all_three_roles(model_database: Database) -> None:
    # 1. Superadmin uploads PNG avatar on admin portal
    superadmin = await actor(
        model_database, role=Role.SUPERADMIN, username="super_avatar", phone="+998901112233"
    )
    async with client_for(superadmin) as client:
        res = await client.post(
            "/api/v1/auth/admin/avatar",
            files={"file": ("photo.png", PNG_BYTES, "image/png")},
        )
        assert res.status_code == 200
        data = res.json()
        avatar_url_1 = data["avatar_url"]
        assert avatar_url_1 is not None
        assert avatar_url_1.startswith("/media/avatars/avatar_")
        assert avatar_url_1.endswith(".png")

        # GET /media/avatars/{filename} serves image
        media_res = await client.get(avatar_url_1)
        assert media_res.status_code == 200
        assert media_res.headers["content-type"].startswith("image/png")
        assert media_res.content == PNG_BYTES

        # Verify GET /me returns updated avatar_url
        me_res = await client.get("/api/v1/auth/admin/me")
        assert me_res.status_code == 200
        assert me_res.json()["avatar_url"] == avatar_url_1

        # 2. Superadmin replaces avatar with JPEG
        res_replace = await client.post(
            "/api/v1/auth/admin/avatar",
            files={"file": ("new_photo.jpg", JPEG_BYTES, "image/jpeg")},
        )
        assert res_replace.status_code == 200
        avatar_url_2 = res_replace.json()["avatar_url"]
        assert avatar_url_2 is not None
        assert avatar_url_2.endswith(".jpg")
        assert avatar_url_2 != avatar_url_1

        # Old avatar is now 404
        old_res = await client.get(avatar_url_1)
        assert old_res.status_code == 404

        # New avatar is 200
        new_res = await client.get(avatar_url_2)
        assert new_res.status_code == 200
        assert new_res.headers["content-type"].startswith("image/jpeg")

        # 3. Superadmin deletes avatar
        del_res = await client.delete("/api/v1/auth/admin/avatar")
        assert del_res.status_code == 200
        assert del_res.json()["avatar_url"] is None

        # Verify GET /me has no avatar
        me_after_del = await client.get("/api/v1/auth/admin/me")
        assert me_after_del.json()["avatar_url"] is None

        # Deleted avatar is now 404
        deleted_res = await client.get(avatar_url_2)
        assert deleted_res.status_code == 404

    # 4. Admin uploads WebP avatar on admin portal
    admin_user = await actor(
        model_database, role=Role.ADMIN, username="admin_avatar", phone="+998902223344"
    )
    async with client_for(admin_user) as client:
        res_admin = await client.post(
            "/api/v1/auth/admin/avatar",
            files={"file": ("profile.webp", WEBP_BYTES, "image/webp")},
        )
        assert res_admin.status_code == 200
        admin_avatar = res_admin.json()["avatar_url"]
        assert admin_avatar.endswith(".webp")

        media_res = await client.get(admin_avatar)
        assert media_res.status_code == 200
        assert media_res.headers["content-type"].startswith("image/webp")

    # 5. Teacher uploads PNG avatar on teacher portal
    teacher_user = await actor(
        model_database, role=Role.TEACHER, username="teacher_avatar", phone="+998903334455"
    )
    async with client_for(teacher_user) as client:
        res_teacher = await client.post(
            "/api/v1/auth/teacher/avatar",
            files={"file": ("teacher.png", PNG_BYTES, "image/png")},
        )
        assert res_teacher.status_code == 200
        teacher_avatar = res_teacher.json()["avatar_url"]
        assert teacher_avatar.endswith(".png")

        media_res = await client.get(teacher_avatar)
        assert media_res.status_code == 200
        assert media_res.headers["content-type"].startswith("image/png")


async def test_avatar_validation_format_and_size(model_database: Database) -> None:
    teacher_user = await actor(model_database, role=Role.TEACHER)
    async with client_for(teacher_user) as client:
        # Invalid format / not an image
        fake_txt = b"Hello world, I am a text file pretending to be an image"
        r1 = await client.post(
            "/api/v1/auth/teacher/avatar",
            files={"file": ("fake.png", fake_txt, "image/png")},
        )
        assert r1.status_code == 422
        assert "formatdagi rasmlar qabul qilinadi" in r1.json()["detail"]

        # Empty file
        r2 = await client.post(
            "/api/v1/auth/teacher/avatar",
            files={"file": ("empty.png", b"", "image/png")},
        )
        assert r2.status_code == 422
        assert "bo‘sh" in r2.json()["detail"]

        # File exceeding 5 MB
        too_large = b"\x89PNG\r\n\x1a\n" + (b"0" * (5 * 1024 * 1024 + 10))
        r3 = await client.post(
            "/api/v1/auth/teacher/avatar",
            files={"file": ("large.png", too_large, "image/png")},
        )
        assert r3.status_code == 413
        assert "5 MB" in r3.json()["detail"]


async def test_avatar_security_path_traversal_and_cross_portal(
    model_database: Database,
) -> None:
    teacher_user = await actor(model_database, role=Role.TEACHER)
    async with client_for(teacher_user) as client:
        # Cross portal: teacher trying admin avatar endpoint
        r_cross = await client.post(
            "/api/v1/auth/admin/avatar",
            files={"file": ("photo.png", PNG_BYTES, "image/png")},
        )
        assert r_cross.status_code == 403

        # Path traversal attempts on media route
        r_traversal_1 = await client.get("/media/avatars/../settings.py")
        assert r_traversal_1.status_code == 404

        r_traversal_2 = await client.get("/media/avatars/%2e%2e%2fsettings.py")
        assert r_traversal_2.status_code == 404

        r_traversal_3 = await client.get("/media/avatars/random_unknown_file.png")
        assert r_traversal_3.status_code == 404


async def test_inactive_staff_cannot_manage_avatar(model_database: Database) -> None:
    person = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        staff_row = await session.get(Staff, person.staff_id)
        assert staff_row is not None
        staff_row.status = Status.INACTIVE
        await session.commit()

    async with client_for(person) as client:
        r_upload = await client.post(
            "/api/v1/auth/teacher/avatar",
            files={"file": ("photo.png", PNG_BYTES, "image/png")},
        )
        assert r_upload.status_code == 401
        assert "Hisob faol emas" in r_upload.json()["detail"]

        r_del = await client.delete("/api/v1/auth/teacher/avatar")
        assert r_del.status_code == 401
        assert "Hisob faol emas" in r_del.json()["detail"]
