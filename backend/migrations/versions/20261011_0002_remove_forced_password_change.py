"""Remove the retired first-login password change flag."""

from alembic import op
import sqlalchemy as sa

revision = "20261011_0002"
down_revision = "20261011_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("dashboard_account", "must_change_password")


def downgrade():
    op.add_column("dashboard_account", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("dashboard_account") as batch:
        batch.alter_column("must_change_password", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
