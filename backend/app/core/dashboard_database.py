from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

from app.core.config import settings
from app.core.db_resources import Database


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
DashboardBase = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))
dashboard_database = Database(settings.dashboard_database_url)
DashboardSessionLocal = dashboard_database.sessions
get_dashboard_db = dashboard_database.session
