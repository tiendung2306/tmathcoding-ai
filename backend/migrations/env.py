from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.core.dashboard_database import DashboardBase
import app.models.dashboard


def run(connection):
    if connection.dialect.name == "mysql" and connection.engine.url.database != settings.DASHBOARD_DB_NAME:
        raise RuntimeError("Migrations may only target DASHBOARD_DB_NAME")
    context.configure(connection=connection, target_metadata=DashboardBase.metadata,
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=settings.dashboard_database_url.set(drivername="mysql+pymysql"),
                      target_metadata=DashboardBase.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    run(context.config.attributes["connection"])
else:
    engine = create_engine(settings.dashboard_migration_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
