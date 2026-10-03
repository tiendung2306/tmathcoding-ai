from sqlalchemy.orm import declarative_base

from app.core.config import settings
from app.core.db_resources import Database


Base = declarative_base()
source_database = Database(settings.source_database_url, read_only=True, pool_size=20)
engine = source_database.engine
AsyncSessionLocal = source_database.sessions
get_db = source_database.session
