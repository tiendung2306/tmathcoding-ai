"""Compatibility aliases; new code should import core.dashboard_database."""

from app.core.dashboard_database import (
    DashboardBase as ConfigBase,
    DashboardSessionLocal as ConfigSessionLocal,
    dashboard_database,
    get_dashboard_db as get_config_db,
)

config_engine = dashboard_database.engine
