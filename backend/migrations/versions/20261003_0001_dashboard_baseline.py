"""Dashboard-owned tables; references to source IDs have no database foreign keys."""
from alembic import context, op
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "20261003_0001"
down_revision = None
branch_labels = None
depends_on = None


def create_table(name, *columns, indexes=()):
    bind = op.get_bind()
    if not context.is_offline_mode() and sa.inspect(bind).has_table(name):
        inspector = sa.inspect(bind)
        actual = {column["name"]: column for column in inspector.get_columns(name)}
        expected = {column.name: column for column in columns}
        if actual.keys() != expected.keys() or inspector.get_foreign_keys(name):
            raise RuntimeError(f"Existing {name} does not match the dashboard baseline")
        impl = MigrationContext.configure(bind).impl
        for key, column in expected.items():
            old = sa.Column(key, actual[key]["type"])
            if impl.compare_type(old, column) or actual[key]["nullable"] != column.nullable:
                raise RuntimeError(f"Existing {name}.{key} does not match the dashboard baseline")
        if inspector.get_pk_constraint(name)["constrained_columns"] != [c.name for c in columns if c.primary_key]:
            raise RuntimeError(f"Existing {name} has a different primary key")
        existing_indexes = {index["name"]: index for index in inspector.get_indexes(name)}
        for index_name, keys in indexes:
            index = existing_indexes.get(index_name)
            if index is None or index["column_names"] != keys or index["unique"]:
                raise RuntimeError(f"Existing {name} has a different index {index_name}")
        return
    op.create_table(name, *columns, mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")
    for index_name, keys in indexes:
        op.create_index(index_name, name, keys)


def upgrade():
    create_table("class_star",
        sa.Column("owner_profile_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("starred_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False),
        indexes=(("ix_class_star_owner_time", ["owner_profile_id", "starred_at"]),))
    create_table("tmath_virtual_class_session",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        indexes=tuple((f"ix_tmath_virtual_class_session_{key}", [key]) for key in ("id", "org_id", "start_time", "end_time")))
    create_table("judge_problem_ai_tag",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
        sa.Column("problem_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("primary_tag_id", sa.Integer(), nullable=False),
        sa.Column("secondary_tag_ids", sa.JSON(), nullable=True),
        sa.Column("bloom_group_id", sa.Integer(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        indexes=tuple((f"ix_judge_problem_ai_tag_{key}", [key]) for key in ("primary_tag_id", "bloom_group_id", "created_at")))


def downgrade():
    op.drop_table("judge_problem_ai_tag")
    op.drop_table("tmath_virtual_class_session")
    op.drop_table("class_star")
