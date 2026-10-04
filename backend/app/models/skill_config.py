from sqlalchemy import Column, DateTime, Integer, JSON

from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now


class SkillConfiguration(DashboardBase):
    __tablename__ = "skill_configuration"

    id = Column(Integer, primary_key=True)
    revision = Column(Integer, nullable=False, default=0)
    published_version = Column(Integer, nullable=False, default=0)
    draft = Column(JSON, nullable=False)
    published = Column(JSON, nullable=True)
    proposals = Column(JSON, nullable=True)
    taxonomy_version = Column(Integer, nullable=False, default=0, server_default="0")
    taxonomy_backup = Column(JSON, nullable=True)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now)


class SkillConfigurationVersion(DashboardBase):
    __tablename__ = "skill_configuration_version"

    version = Column(Integer, primary_key=True)
    document = Column(JSON, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
