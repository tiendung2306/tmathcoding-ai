from app.services.source_gateway import SourceClass, SourceGateway


async def get_visible_class(gateway: SourceGateway, org_id: int, teacher_id: int) -> SourceClass:
    """Resolve a class through the source API, which applies the caller's access scope."""
    return await gateway.get_class(org_id, actor_profile_id=teacher_id)
