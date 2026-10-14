from sqlalchemy.orm import declarative_base

# Legacy source models retain metadata for offline tools and migration fixtures.
# Runtime application code must access source records through SourceGateway.
Base = declarative_base()
