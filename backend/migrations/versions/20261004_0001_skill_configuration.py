"""Versioned draft and published skill forests owned by the dashboard."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0001"
down_revision = "20261003_0001"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "skill_configuration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("published", sa.JSON(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "skill_configuration_version",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    from datetime import datetime, timezone
    op.bulk_insert(table, [{"id": 1, "revision": 0, "published_version": 0,
        "draft": {"nodes": [{"id": "other", "title": "Khác",
            "description": "Các dạng bài chưa thuộc nhóm kỹ năng cụ thể.",
            "parent_id": None, "target": 10}], "assignments": {}},
        "published": None, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}])


def downgrade():
    op.drop_table("skill_configuration_version")
    op.drop_table("skill_configuration")
