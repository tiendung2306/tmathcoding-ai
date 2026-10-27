from sqlalchemy import Column, Date, DateTime, Float, Integer, MetaData, SmallInteger, String, Table, Text

metadata = MetaData()
profile = Table(
    "judge_profile", metadata,
    Column("id", Integer, primary_key=True), Column("user_id", Integer),
    Column("name", String), Column("points", Float), Column("problem_count", Integer),
    Column("display_rank", String), Column("super_admin", SmallInteger),
)
user = Table(
    "auth_user", metadata,
    Column("id", Integer, primary_key=True), Column("username", String),
    Column("email", String), Column("is_active", SmallInteger),
)
school_year = Table(
    "judge_schoolyear", metadata,
    Column("id", Integer, primary_key=True), Column("start", Date), Column("finish", Date),
)
organization = Table(
    "judge_organization", metadata,
    Column("id", Integer, primary_key=True), Column("name", String),
    Column("creation_date", DateTime), Column("year_id", Integer), Column("is_hidden", SmallInteger),
)
organization_admin = Table(
    "judge_organization_admins", metadata,
    Column("id", Integer, primary_key=True), Column("profile_id", Integer), Column("organization_id", Integer),
)
profile_organization = Table(
    "judge_profile_organizations", metadata,
    Column("id", Integer, primary_key=True), Column("profile_id", Integer), Column("organization_id", Integer),
)
contest = Table(
    "judge_contest", metadata,
    Column("id", Integer, primary_key=True), Column("key", String), Column("name", String),
    Column("start_time", DateTime), Column("end_time", DateTime), Column("is_visible", SmallInteger),
    Column("is_private", SmallInteger), Column("is_organization_private", SmallInteger),
    Column("is_public_contest", SmallInteger), Column("version_update", Integer),
)
contest_organization = Table(
    "judge_contest_organizations", metadata,
    Column("contest_id", Integer, primary_key=True), Column("organization_id", Integer, primary_key=True),
)
contest_author = Table(
    "judge_contest_authors", metadata,
    Column("contest_id", Integer, primary_key=True), Column("profile_id", Integer, primary_key=True),
)
contest_curator = Table(
    "judge_contest_curators", metadata,
    Column("contest_id", Integer, primary_key=True), Column("profile_id", Integer, primary_key=True),
)
problem = Table(
    "judge_problem", metadata,
    Column("id", Integer, primary_key=True), Column("code", String), Column("name", String),
    Column("description", Text), Column("time_limit", Float), Column("memory_limit", Integer),
    Column("points", Float), Column("is_public", SmallInteger),
    Column("is_organization_private", SmallInteger), Column("classes_id", Integer),
    Column("group_id", Integer), Column("version_update", Integer),
)
problem_type_catalog = Table(
    "judge_problemtype", metadata,
    Column("id", Integer, primary_key=True), Column("name", String),
    Column("full_name", String), Column("priority", SmallInteger),
)
problem_type = Table(
    "judge_problem_types", metadata,
    Column("id", Integer, primary_key=True), Column("problem_id", Integer),
    Column("problemtype_id", Integer),
)
problem_group = Table(
    "judge_problemgroup", metadata,
    Column("id", Integer, primary_key=True), Column("name", String),
    Column("full_name", String),
)
language = Table(
    "judge_language", metadata,
    Column("id", Integer, primary_key=True), Column("key", String), Column("name", String),
    Column("common_name", String),
)
submission = Table(
    "judge_submission", metadata,
    Column("id", Integer, primary_key=True), Column("date", DateTime),
    Column("judged_date", DateTime), Column("rejudged_date", DateTime),
    Column("version_update", String), Column("time", Float), Column("memory", Float),
    Column("points", Float), Column("status", String), Column("result", String),
    Column("error", Text), Column("user_id", Integer), Column("problem_id", Integer),
    Column("language_id", Integer),
)
submission_source = Table(
    "judge_submissionsource", metadata,
    Column("id", Integer, primary_key=True), Column("submission_id", Integer), Column("source", Text),
)
submission_testcase = Table(
    "judge_submissiontestcase", metadata,
    Column("id", Integer, primary_key=True), Column("case", Integer), Column("status", String),
    Column("time", Float), Column("memory", Float), Column("points", Float), Column("total", Float),
    Column("batch", Integer), Column("feedback", String), Column("extended_feedback", Text),
    Column("output", Text), Column("submission_id", Integer),
)
