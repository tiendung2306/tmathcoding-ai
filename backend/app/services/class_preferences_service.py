
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_preferences import ClassStar
from app.core.time import utc_now
from app.models.dmoj import JudgeOrganization, JudgeOrganizationAdmins, JudgeProfile
from app.schemas.teacher import ClassStarResponse


async def set_class_star(
    db: AsyncSession, config_db: AsyncSession, teacher_id: int, org_id: int, starred: bool,
) -> ClassStarResponse:
    profile = (await db.execute(
        select(JudgeProfile).where(JudgeProfile.id == teacher_id)
    )).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=403, detail="Bạn không có quyền lưu lớp này.")
    visible = select(JudgeOrganization.id).where(JudgeOrganization.id == org_id)
    if not profile.super_admin:
        visible = visible.where(select(JudgeOrganizationAdmins.id).where(
            JudgeOrganizationAdmins.organization_id == JudgeOrganization.id,
            JudgeOrganizationAdmins.profile_id == teacher_id,
        ).exists())
    if (await db.execute(visible)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp trong danh sách được phép xem.")

    key = {"owner_profile_id": teacher_id, "organization_id": org_id}
    if starred:
        values = {**key, "starred_at": utc_now()}
        # Idempotent PUT preserves the original timestamp even under concurrent requests.
        if config_db.get_bind().dialect.name == "sqlite":
            statement = sqlite_insert(ClassStar).values(**values).on_conflict_do_nothing()
        else:
            statement = mysql_insert(ClassStar).values(**values).on_duplicate_key_update(
                starred_at=ClassStar.starred_at,
            )
        await config_db.execute(statement)
    else:
        await config_db.execute(delete(ClassStar).where(
            ClassStar.owner_profile_id == teacher_id, ClassStar.organization_id == org_id,
        ))
    await config_db.commit()
    timestamp = (await config_db.execute(select(ClassStar.starred_at).where(
        ClassStar.owner_profile_id == teacher_id, ClassStar.organization_id == org_id,
    ))).scalar_one_or_none()
    return ClassStarResponse(organization_id=org_id, starred_at=timestamp)
