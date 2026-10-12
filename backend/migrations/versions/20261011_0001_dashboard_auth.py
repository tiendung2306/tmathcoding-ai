"""Dashboard accounts and revocable sessions."""

from alembic import op
import sqlalchemy as sa

revision = "20261011_0001"
down_revision = "20261004_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dashboard_account",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("admin_slot", sa.SmallInteger(), nullable=False),
        sa.Column("source_profile_id", sa.Integer(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_dashboard_account"),
        sa.UniqueConstraint("username", name="uq_dashboard_account_username"),
        sa.UniqueConstraint("admin_slot", name="uq_dashboard_account_admin_slot"),
        sa.UniqueConstraint("source_profile_id", name="uq_dashboard_account_source_profile_id"),
        sa.CheckConstraint("username = 'admin' AND role = 'admin' AND admin_slot = 1", name="ck_dashboard_account_single_admin"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "dashboard_auth_session",
        sa.Column("token_hash", sa.String(64), primary_key=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["dashboard_account.id"], name="fk_dashboard_auth_session_account_id_dashboard_account", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash", name="pk_dashboard_auth_session"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_dashboard_auth_session_account_id", "dashboard_auth_session", ["account_id"])
    op.create_index("ix_dashboard_auth_session_expires_at", "dashboard_auth_session", ["expires_at"])


def downgrade():
    op.drop_index("ix_dashboard_auth_session_expires_at", table_name="dashboard_auth_session")
    op.drop_index("ix_dashboard_auth_session_account_id", table_name="dashboard_auth_session")
    op.drop_table("dashboard_auth_session")
    op.drop_table("dashboard_account")
