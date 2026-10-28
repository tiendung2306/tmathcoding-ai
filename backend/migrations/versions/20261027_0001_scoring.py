"""Versioned scoring snapshots and publication."""
from alembic import op
import sqlalchemy as sa

revision = "20261027_0001"
down_revision = "20261011_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scoring_state", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("active_run_id", sa.String(32)))
    op.create_table("scoring_run", sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False), sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False), sa.Column("base_run_id", sa.String(32)),
        sa.Column("points_run_id", sa.String(32)), sa.Column("lease_token", sa.String(32)),
        sa.Column("lease_until", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()), sa.Column("published_at", sa.DateTime()),
        sa.Column("source_as_of", sa.DateTime()), sa.Column("manifest", sa.JSON()),
        sa.Column("diagnostics", sa.JSON()), sa.Column("progress", sa.String(255), nullable=False),
        sa.Column("error", sa.Text()))
    op.create_index("ix_scoring_run_status", "scoring_run", ["status"])
    op.create_table("scoring_item", sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column("problem_id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False), sa.Column("source_group_id", sa.Integer()),
        sa.Column("grade", sa.String(1)), sa.Column("points", sa.Integer()), sa.Column("difficulty", sa.Float()),
        sa.Column("attempted", sa.Integer(), nullable=False), sa.Column("solved", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(24), nullable=False))
    op.create_table("scoring_profile", sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(150), nullable=False), sa.Column("total_points", sa.BigInteger(), nullable=False),
        sa.Column("solved_count", sa.Integer(), nullable=False), sa.Column("unscored_count", sa.Integer(), nullable=False))
    op.create_index("ix_scoring_profile_leaderboard", "scoring_profile", ["run_id", "total_points", "profile_id"])
    op.create_table("scoring_pair", sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.Integer(), primary_key=True), sa.Column("problem_id", sa.Integer(), primary_key=True),
        sa.Column("has_ac", sa.Boolean(), nullable=False), sa.Column("first_ac_at", sa.DateTime()))
    op.create_index("ix_scoring_pair_problem", "scoring_pair", ["run_id", "problem_id", "has_ac"])
    policy = {"bands": {grade: {"minimum": 100 + 400 * i, "maximum": 450 + 400 * i,
              "initial": 300 + 400 * i} for i, grade in enumerate("ABCDEF")},
              "overrides": {}, "min_attempted": 30, "min_each_outcome": 5}
    op.bulk_insert(sa.table("scoring_state", sa.column("id", sa.Integer()),
        sa.column("revision", sa.Integer()), sa.column("policy", sa.JSON())),
        [{"id": 1, "revision": 1, "policy": policy}])


def downgrade():
    for table in ("scoring_pair", "scoring_profile", "scoring_item", "scoring_run", "scoring_state"):
        op.drop_table(table)
