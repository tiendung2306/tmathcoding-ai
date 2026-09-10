from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, SmallInteger, JSON
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
    about = Column(Text)  # Schema thật của tmath dùng 'about' (không phải 'description')
    creation_date = Column(DateTime)
    is_open = Column(SmallInteger, default=1)
    slots = Column(Integer)
    access_code = Column(String(7))
    logo_override_image = Column(String(150))
    rate = Column(Integer, default=0)
    year_id = Column(Integer)
    is_hidden = Column(SmallInteger, default=0)

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

class AuthUser(Base):
    """Django auth_user: nguồn username thật của học sinh/giáo viên."""
    __tablename__ = "auth_user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, index=True)
    first_name = Column(String(150), default="")
    last_name = Column(String(150), default="")
    email = Column(String(254), default="")
    is_active = Column(SmallInteger, default=1)

class JudgeProblemGroup(Base):
    """Nhóm mức độ bài toán: mapping Bloom theo dữ liệu thật của tmath:
    4=A(Nhớ), 5=B(Hiểu), 6=C(Vận dụng), 7=D(Phân tích), 8=E(Đánh giá), 13=F(Đặc biệt)."""
    __tablename__ = "judge_problemgroup"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20))
    full_name = Column(String(100))

class JudgeProblemAiTag(Base):
    """Lưu trữ kết quả tự động gắn nhãn chủ đề và mức độ Bloom của AI (Pipeline F3.1)."""
    __tablename__ = "judge_problem_ai_tag"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    problem_id = Column(Integer, ForeignKey("judge_problem.id"), unique=True, index=True, nullable=False)
    primary_tag_id = Column(Integer, ForeignKey("judge_problemtype.id"), index=True, nullable=False)
    secondary_tag_ids = Column(JSON, nullable=True)  # List[int]
    bloom_group_id = Column(Integer, ForeignKey("judge_problemgroup.id"), index=True, nullable=True)
    reasoning = Column(Text, nullable=True)
    model = Column(String(100), default="Qwen3.8-4B-GGUF")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class JudgeLanguage(Base):
    __tablename__ = "judge_language"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(10), unique=True)
    name = Column(String(20))
    common_name = Column(String(10))

class JudgeSubmissionTestcase(Base):
    __tablename__ = "judge_submissiontestcase"

    id = Column(Integer, primary_key=True, index=True)
    case = Column(Integer)
    status = Column(String(3))
    time = Column(Float)
    memory = Column(Float)
    points = Column(Float)
    total = Column(Float)
    batch = Column(Integer)
    feedback = Column(String(50))
    extended_feedback = Column(Text)
    output = Column(Text)
    submission_id = Column(Integer, ForeignKey("judge_submission.id"), index=True)

