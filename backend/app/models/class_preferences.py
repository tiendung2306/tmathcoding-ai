
from sqlalchemy import Column, DateTime, Index, Integer
from sqlalchemy.dialects.mysql import DATETIME

from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now


class ClassStar(DashboardBase):
    __tablename__ = "class_star"
    __table_args__ = (Index("ix_class_star_owner_time", "owner_profile_id", "starred_at"),)

    # References to the source DB stay logical; config metadata is independent.
    owner_profile_id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, primary_key=True)
    starred_at = Column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False,
        default=utc_now,
    )
