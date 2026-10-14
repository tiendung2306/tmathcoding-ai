import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


def source_url() -> str | URL:
    if os.getenv("SOURCE_DATABASE_URL"):
        return os.environ["SOURCE_DATABASE_URL"]
    host = os.getenv("SOURCE_DB_HOST", "localhost")
    port = os.getenv("SOURCE_DB_PORT", "3306")
    user = os.getenv("SOURCE_DB_USER", "source_readonly")
    password = os.getenv("SOURCE_DB_PASSWORD", "")
    name = os.getenv("SOURCE_DB_NAME", "tmathcoding")
    return URL.create(
        "mysql+pymysql", username=user, password=password, host=host,
        port=int(port), database=name, query={"charset": "utf8mb4"},
    )


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(source_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)


def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
