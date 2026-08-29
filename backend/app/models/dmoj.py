from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, SmallInteger
from app.core.database import Base

class JudgeProfile(Base):
    __tablename__ = "judge_profile"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_user.id"), unique=True)
    name = Column(String(100))
    points = Column(Float, default=0.0)
    performance_points = Column(Float, default=0.0)
    problem_count = Column(Integer, default=0)
    display_rank = Column(String(50), default="user")
    super_admin = Column(SmallInteger, default=0)

class JudgeOrganization(Base):
    __tablename__ = "judge_organization"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128))
    slug = Column(String(128), unique=True)
    short_name = Column(String(20))
    description = Column(Text)
    is_open = Column(SmallInteger, default=1)

class JudgeOrganizationAdmins(Base):
    __tablename__ = "judge_organization_admins"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("judge_profile.id"), index=True)
    organization_id = Column(Integer, ForeignKey("judge_organization.id"), index=True)

class JudgeProfileOrganizations(Base):
    __tablename__ = "judge_profile_organizations"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("judge_profile.id"), index=True)
    organization_id = Column(Integer, ForeignKey("judge_organization.id"), index=True)

class JudgeProblem(Base):
    __tablename__ = "judge_problem"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True)
    name = Column(String(255))
    description = Column(Text)
    time_limit = Column(Float, default=1.0)
    memory_limit = Column(Integer, default=256000)
    points = Column(Float, default=100.0)
    group_id = Column(Integer, ForeignKey("judge_problemgroup.id"), index=True)  # Bloom level
    classes_id = Column(Integer, ForeignKey("judge_problemclass.id"), index=True)

class JudgeProblemtype(Base):
    __tablename__ = "judge_problemtype"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20))
    full_name = Column(String(100))
    priority = Column(SmallInteger, default=0)

class JudgeProblemTypes(Base):
    __tablename__ = "judge_problem_types"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("judge_problem.id"), index=True)
    problemtype_id = Column(Integer, ForeignKey("judge_problemtype.id"), index=True)

class JudgeSubmission(Base):
    __tablename__ = "judge_submission"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, index=True)
    time = Column(Float)
    memory = Column(Float)
    points = Column(Float)
    status = Column(String(2))
    result = Column(String(3), index=True)
    error = Column(Text)
    user_id = Column(Integer, ForeignKey("judge_profile.id"), index=True)
    problem_id = Column(Integer, ForeignKey("judge_problem.id"), index=True)
    language_id = Column(Integer, index=True)

class JudgeSubmissionsource(Base):
    __tablename__ = "judge_submissionsource"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("judge_submission.id"), unique=True, index=True)
    source = Column(Text)
