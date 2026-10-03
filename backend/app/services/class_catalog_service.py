from sqlalchemy import DateTime, String, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dmoj import (
    AuthUser,
    JudgeOrganization,
    JudgeOrganizationAdmins,
    JudgeProfile,
    JudgeProfileOrganizations,
    JudgeSchoolYear,
)
from app.models.virtual_class import VirtualClassSession
from app.models.class_preferences import ClassStar
from app.schemas.teacher import ClassManager, ClassPage, ClassSortField, ClassSummary, SortOrder


async def get_class_page(
    db: AsyncSession,
    teacher_id: int,
    page: int,
    page_size: int,
    q: str,
    sort_by: ClassSortField,
    sort_order: SortOrder,
    config_db: AsyncSession,
    starred_only: bool = False,
) -> ClassPage:
    stars = dict((await config_db.execute(
        select(ClassStar.organization_id, ClassStar.starred_at)
        .where(ClassStar.owner_profile_id == teacher_id)
    )).all())
    profile = (
        await db.execute(select(JudgeProfile).where(JudgeProfile.id == teacher_id))
    ).scalar_one_or_none()
    filters = []
    if not (profile and profile.super_admin):
        filters.append(
            select(JudgeOrganizationAdmins.id)
            .where(
                JudgeOrganizationAdmins.organization_id == JudgeOrganization.id,
                JudgeOrganizationAdmins.profile_id == teacher_id,
            )
            .exists()
        )

    query = q.strip()
    if query:
        filters.append(or_(
            JudgeOrganization.name.contains(query, autoescape=True),
            cast(JudgeOrganization.id, String).contains(query, autoescape=True),
        ))
    if starred_only:
        filters.append(JudgeOrganization.id.in_(stars))

    total = (
        await db.execute(select(func.count()).select_from(JudgeOrganization).where(*filters))
    ).scalar_one()
    total_pages = (total + page_size - 1) // page_size
    # Keep the requested page valid when the filtered dataset shrinks.
    page = min(page, max(1, total_pages))

    members = (
        select(
            JudgeProfileOrganizations.organization_id,
            func.count(JudgeProfileOrganizations.id).label("member_count"),
        )
        .group_by(JudgeProfileOrganizations.organization_id)
        .subquery()
    )
    session_rows = (await config_db.execute(select(
            VirtualClassSession.org_id,
            # An ended session contributes its end time; an ongoing one its start time.
            func.max(func.coalesce(
                VirtualClassSession.end_time, VirtualClassSession.start_time,
            )).label("last_session_at"),
        ).group_by(VirtualClassSession.org_id))).all()
    latest_sessions = {row.org_id: row.last_session_at for row in session_rows}
    last_session_at = (case(latest_sessions, value=JudgeOrganization.id, else_=None)
                       if latest_sessions else literal(None, type_=DateTime)).label("last_session_at")
    member_count = func.coalesce(members.c.member_count, 0).label("member_count")
    fields = {
        "creation_date": JudgeOrganization.creation_date,
        "name": JudgeOrganization.name,
        "member_count": member_count,
        "id": JudgeOrganization.id,
        "last_session_at": last_session_at,
    }
    field = fields[sort_by]
    starred_at = (
        case(stars, value=JudgeOrganization.id, else_=None)
        if stars else literal(None, type_=DateTime)
    ).label("starred_at")
    direction = field.asc() if sort_order == "asc" else field.desc()
    # MySQL does not support NULLS LAST; sort null values separately in both directions.
    ordering = [direction]
    if sort_by in ("creation_date", "last_session_at"):
        ordering.insert(0, field.is_(None).asc())
    if sort_by != "id":
        ordering.append(JudgeOrganization.id.asc())
    ordering = [starred_at.is_(None).asc(), starred_at.desc(), *ordering]

    result = await db.execute(
        select(
            JudgeOrganization.id,
            JudgeOrganization.name,
            JudgeOrganization.creation_date,
            JudgeSchoolYear.start.label("year_start"),
            JudgeSchoolYear.finish.label("year_finish"),
            member_count,
            last_session_at,
            starred_at,
        )
        .outerjoin(members, members.c.organization_id == JudgeOrganization.id)
        .outerjoin(JudgeSchoolYear, JudgeSchoolYear.id == JudgeOrganization.year_id)
        .where(*filters)
        .order_by(*ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()
    managers: dict[int, list[ClassManager]] = {}
    if rows:
        # Fetch managers for this page only, without multiplying class or member rows.
        manager_rows = await db.execute(
            select(
                JudgeOrganizationAdmins.organization_id,
                JudgeProfile.id,
                JudgeProfile.name,
                AuthUser.username,
            )
            .select_from(JudgeOrganizationAdmins)
            .join(JudgeProfile, JudgeProfile.id == JudgeOrganizationAdmins.profile_id)
            .outerjoin(AuthUser, AuthUser.id == JudgeProfile.user_id)
            .where(JudgeOrganizationAdmins.organization_id.in_([row.id for row in rows]))
            .distinct()
            .order_by(JudgeProfile.id.asc())
        )
        for manager in manager_rows.all():
            managers.setdefault(manager.organization_id, []).append(ClassManager(
                id=manager.id,
                name=(manager.name or "").strip() or manager.username or f"Profile {manager.id}",
            ))
    return ClassPage(
        items=[ClassSummary(
            id=row.id,
            name=row.name or f"Lớp {row.id}",
            member_count=row.member_count,
            school_year=(f"{row.year_start.year}-{row.year_finish.year}"
                         if row.year_start and row.year_finish else None),
            managers=managers.get(row.id, []),
            creation_date=row.creation_date,
            last_session_at=row.last_session_at,
            starred_at=row.starred_at,
        ) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
