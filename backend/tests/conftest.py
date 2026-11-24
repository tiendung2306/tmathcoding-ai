import pytest

from app.core.dashboard_auth import reset_access_cache
from app.core.request_cache import reset_request_cache
from app.services.class_student_service import reset_roster_cache


@pytest.fixture(autouse=True)
def isolated_roster_cache():
    """Module-level caches must not leak data between tests."""
    reset_roster_cache()
    reset_access_cache()
    reset_request_cache()
    yield
    reset_roster_cache()
    reset_access_cache()
