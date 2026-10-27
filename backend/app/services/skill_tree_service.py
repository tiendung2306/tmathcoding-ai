import asyncio

from fastapi import HTTPException

from app.schemas.student import SkillTreeResponse, SkillTreeNode, AlgorithmRadar
from app.services.algorithm_competency_service import algorithm_competency_service
from app.services.source_gateway import SourceGateway


BENCHMARKS = {"all": 10.0, "1d": 10.0, "7d": 2.0, "30d": 4.0, "1y": 8.0}


def _compact_forest(nodes: list[dict]) -> list[dict]:
    return [{
        "id": node["id"], "title": node["title"], "description": node["description"],
        "problem_count": node["problem_count"], "ac_count": node["ac_count"],
        "attempted_count": node["attempted_count"],
        "children": _compact_forest(node["children"]),
    } for node in nodes]


class SkillTreeService:
    @staticmethod
    async def _all_tags(source: SourceGateway, actor_profile_id: int):
        tags = []
        cursor = None
        seen: set[str] = set()
        version = None
        while True:
            page, _etag, not_modified = await source.list_tags(
                actor_profile_id=actor_profile_id, cursor=cursor, limit=100,
            )
            if not_modified or page is None:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn không trả danh sách tag.")
            if page.catalog_version is None:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu phiên bản danh mục tag.")
            if version is None:
                version = page.catalog_version
            elif version != page.catalog_version:
                raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải cây kỹ năng.")
            tags.extend(page.items)
            if not page.has_more:
                return tags, version
            cursor = page.next_cursor
            if not cursor or cursor in seen:
                raise HTTPException(502, "Dịch vụ dữ liệu nguồn trả phân trang tag không hợp lệ.")
            seen.add(cursor)

    @staticmethod
    async def get_student_skill_tree(
        user_id: int,
        source: SourceGateway,
        time_range: str = "all",
        dashboard_db=None,
        *, actor_profile_id: int,
    ) -> SkillTreeResponse:
        profile, initial = await asyncio.gather(
            source.get_student(user_id, actor_profile_id=actor_profile_id),
            source.aggregate_students([user_id], actor_profile_id=actor_profile_id, tag_groups=[]),
        )
        cutoff = algorithm_competency_service.get_cutoff_date(
            time_range, initial.reference_now,
        )
        if dashboard_db is not None:
            from app.services.skill_config_service import configuration, preview
            from app.schemas.skill_config import SkillDocument
            config = await configuration(dashboard_db)
            if config.published is not None:
                forest = await preview(
                    SkillDocument.model_validate(config.published), source, user_id, cutoff,
                    actor_profile_id=actor_profile_id, include_evidence=False,
                    student_verified=True,
                )
                if forest["catalog_version"] != initial.catalog_version:
                    raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải cây kỹ năng.")
                radar = AlgorithmRadar(time_range=time_range, axes=[{
                    "key": root["id"], "title": root["title"],
                    "ac_count": root["ac_count"], "attempted_count": root["attempted_count"],
                    "problem_count": root["problem_count"],
                } for root in forest["roots"]])
                return SkillTreeResponse(
                    user_id=user_id, student_name=profile.name or f"User {user_id}",
                    time_range=time_range, bloom_radar=radar, skill_tree_nodes=[],
                    skill_forest=_compact_forest(forest["roots"]),
                    configuration_version=config.published_version,
                )
        aggregate = initial
        if cutoff is not None:
            aggregate = await source.aggregate_students(
                [user_id], actor_profile_id=actor_profile_id, date_from=cutoff,
                date_to=None, tag_groups=[],
            )
            if (aggregate.catalog_version != initial.catalog_version
                    or aggregate.reference_now != initial.reference_now):
                raise HTTPException(409, "Danh mục hoặc mốc dữ liệu đã thay đổi trong lúc tải cây kỹ năng.")
        student = next((item for item in aggregate.students if item.profile_id == user_id), None)
        if student is None:
            raise HTTPException(502, "Dịch vụ dữ liệu nguồn thiếu thống kê học sinh.")
        tags, tags_version = await SkillTreeService._all_tags(source, actor_profile_id)
        if tags_version != aggregate.catalog_version:
            raise HTTPException(409, "Danh mục đã thay đổi trong lúc tải cây kỹ năng.")

        tag_counts = {item.tag_id: item.solved_unique_count for item in student.tag_stats}
        target = BENCHMARKS.get(time_range, BENCHMARKS["all"])
        nodes = []
        for tag in tags:
            count = tag_counts.get(tag.tag_id, 0)
            mastery = min(100.0, count / target * 100.0) if target else 0.0
            status = "LOCKED"
            if mastery >= 75:
                status = "GREEN"
            elif mastery >= 25:
                status = "YELLOW"
            elif count > 0:
                status = "RED"
            nodes.append(SkillTreeNode(
                topic_id=tag.tag_id,
                key=tag.key or f"T{tag.tag_id}",
                name=tag.title or tag.key or f"Topic {tag.tag_id}",
                category="Chủ đề",
                mastery_score=round(mastery, 1),
                status=status,
            ))
        radar = await algorithm_competency_service.get_student_radar(
            user_id, time_range, source, dashboard_db,
            actor_profile_id=actor_profile_id,
        )
        return SkillTreeResponse(
            user_id=user_id, student_name=profile.name or f"User {user_id}",
            time_range=time_range, bloom_radar=radar, skill_tree_nodes=nodes,
        )


skill_tree_service = SkillTreeService()
