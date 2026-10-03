from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory


def migration_config(connection=None) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


async def ensure_schema_current(engine):
    expected = set(ScriptDirectory.from_config(migration_config()).get_heads())

    def check(connection):
        current = set(MigrationContext.configure(connection).get_current_heads())
        if current != expected:
            raise RuntimeError("Dashboard schema is outdated. Run: python -m app.db.migrate upgrade head")

    async with engine.connect() as connection:
        await connection.run_sync(check)
