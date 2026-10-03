from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dmoj import JudgeOrganization, JudgeOrganizationAdmins, JudgeProfile


async def get_visible_class(db: AsyncSession, org_id: int, teacher_id: int):
    profile = (await db.execute(
        select(JudgeProfile).where(JudgeProfile.id == teacher_id)
    )).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem lớp này.")
    stmt = select(JudgeOrganization).where(JudgeOrganization.id == org_id)
    if not profile.super_admin:
        stmt = stmt.where(select(JudgeOrganizationAdmins.id).where(
            JudgeOrganizationAdmins.organization_id == JudgeOrganization.id,
            JudgeOrganizationAdmins.profile_id == teacher_id,
        ).exists())
    organization = (await db.execute(stmt)).scalar_one_or_none()
    if organization is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp trong danh sách được phép xem.")
    return organization
