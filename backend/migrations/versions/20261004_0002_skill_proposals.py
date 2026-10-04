"""Persist the current skill tag proposal list in the dashboard."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0002"
down_revision = "20261004_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("skill_configuration", sa.Column("proposals", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("skill_configuration", "proposals")
