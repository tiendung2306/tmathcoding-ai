from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session


class ReadOnlySession(Session):
    pass


@event.listens_for(ReadOnlySession, "before_flush")
def reject_source_writes(session, flush_context, instances):
    if session.new or session.dirty or session.deleted:
        raise RuntimeError("The source database is read-only; persist dashboard data in DashboardBase")


class Database:
    """One engine/session pool per database; lifecycle owned by the application."""

    def __init__(self, url: URL, *, read_only: bool = False, pool_size: int = 5):
        self.engine = create_async_engine(url, pool_pre_ping=True, pool_size=pool_size, max_overflow=pool_size)
        self.sessions = async_sessionmaker(
            self.engine, expire_on_commit=False,
            sync_session_class=ReadOnlySession if read_only else Session,
        )

    async def session(self):
        async with self.sessions() as session:
            yield session

    async def close(self):
        await self.engine.dispose()
