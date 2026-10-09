from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from neoavlod.api.deps import AdminDependency, SessionDependency
from neoavlod.models import Group, Role, Staff, Student
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission, has_permission

router = APIRouter(prefix="/api/v1/admin/dashboard", tags=["admin-dashboard"])


class DashboardStaffBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    teachers: int
    admins: int
    superadmins: int


class DashboardStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    groups_count: int | None = None
    students_count: int | None = None
    staff_count: int | None = None
    staff_breakdown: DashboardStaffBreakdown | None = None


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    session: SessionDependency,
    identity: AdminDependency,
) -> DashboardStatsResponse:
    staff = identity.staff

    groups_count: int | None = None
    if has_permission(staff, Permission.GROUPS_READ):
        count = await session.scalar(
            select(func.count(Group.id)).where(Group.status == Status.ACTIVE)
        )
        groups_count = count or 0

    students_count: int | None = None
    if has_permission(staff, Permission.STUDENTS_READ):
        count = await session.scalar(
            select(func.count(Student.id)).where(Student.status == Status.ACTIVE)
        )
        students_count = count or 0

    staff_count: int | None = None
    staff_breakdown: DashboardStaffBreakdown | None = None
    if has_permission(staff, Permission.STAFF_MANAGE):
        total = await session.scalar(
            select(func.count(Staff.id)).where(Staff.status == Status.ACTIVE)
        )
        teachers = await session.scalar(
            select(func.count(Staff.id)).where(
                Staff.status == Status.ACTIVE, Staff.role == Role.TEACHER
            )
        )
        admins = await session.scalar(
            select(func.count(Staff.id)).where(
                Staff.status == Status.ACTIVE, Staff.role == Role.ADMIN
            )
        )
        superadmins = await session.scalar(
            select(func.count(Staff.id)).where(
                Staff.status == Status.ACTIVE, Staff.role == Role.SUPERADMIN
            )
        )
        staff_count = total or 0
        staff_breakdown = DashboardStaffBreakdown(
            teachers=teachers or 0,
            admins=admins or 0,
            superadmins=superadmins or 0,
        )

    return DashboardStatsResponse(
        groups_count=groups_count,
        students_count=students_count,
        staff_count=staff_count,
        staff_breakdown=staff_breakdown,
    )
