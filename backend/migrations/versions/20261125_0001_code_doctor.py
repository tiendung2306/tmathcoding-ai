"""Code Doctor solution bank, reports and teacher feedback."""

from alembic import op
import sqlalchemy as sa

revision = "20261125_0001"
down_revision = "20261027_0001"
branch_labels = None
depends_on = None

TABLE_OPTIONS = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci")


def upgrade():
    op.create_table(
        "doctor_solution_approach",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("key_ideas", sa.JSON()),
        sa.Column("pitfalls", sa.JSON()),
        sa.Column("time_complexity", sa.String(64)),
        sa.Column("control_flow", sa.String(512), nullable=False),
        sa.Column("techniques", sa.JSON(), nullable=False),
        sa.Column("complexity_rank", sa.Float(), nullable=False),
        sa.Column("representative_submission_id", sa.Integer(), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_canonical", sa.Boolean(), nullable=False),
        sa.Column("card_origin", sa.String(16), nullable=False),
        sa.Column("reviewed_by", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_doctor_solution_approach"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_doctor_solution_approach_problem_id", "doctor_solution_approach", ["problem_id"])
    op.create_table(
        "doctor_solution_member",
        sa.Column("approach_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("language_key", sa.String(32)),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["approach_id"], ["doctor_solution_approach.id"],
                                name="fk_doctor_solution_member_approach_id_doctor_solution_approach",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("approach_id", "submission_id", name="pk_doctor_solution_member"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_doctor_solution_member_problem", "doctor_solution_member", ["problem_id", "submission_id"])
    op.create_table(
        "doctor_report",
        sa.Column("submission_id", sa.Integer(), primary_key=True, autoincrement=False, nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("approach_id", sa.Integer()),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255)),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("submission_id", name="pk_doctor_report"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_doctor_report_problem_id", "doctor_report", ["problem_id"])
    op.create_table(
        "doctor_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("teacher_profile_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_doctor_feedback"),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_doctor_feedback_submission_id", "doctor_feedback", ["submission_id"])


def downgrade():
    op.drop_index("ix_doctor_feedback_submission_id", table_name="doctor_feedback")
    op.drop_table("doctor_feedback")
    op.drop_index("ix_doctor_report_problem_id", table_name="doctor_report")
    op.drop_table("doctor_report")
    op.drop_index("ix_doctor_solution_member_problem", table_name="doctor_solution_member")
    op.drop_table("doctor_solution_member")
    op.drop_index("ix_doctor_solution_approach_problem_id", table_name="doctor_solution_approach")
    op.drop_table("doctor_solution_approach")
