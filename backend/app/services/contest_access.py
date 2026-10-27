from app.services.source_gateway import SourceContest, SourceGateway


async def get_visible_contest(
    gateway: SourceGateway,
    contest_id: int,
    actor_profile_id: int,
) -> SourceContest:
    """Resolve one contest by ID through the source API's visibility checks."""
    return await gateway.get_teacher_contest(
        actor_profile_id,
        contest_id,
        actor_profile_id=actor_profile_id,
    )
