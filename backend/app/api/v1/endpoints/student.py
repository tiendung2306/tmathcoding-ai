from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.student import SkillTreeResponse
from app.schemas.ai import CodeDoctorRequest, CodeDoctorResponse
from app.services.skill_tree_service import skill_tree_service
from app.services.code_doctor_service import code_doctor_service

router = APIRouter()

@router.get("/{user_id}/skill-tree", response_model=SkillTreeResponse)
async def get_student_skill_tree(user_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch 99-Node Skill Tree & Bloom Radar for a student."""
    return await skill_tree_service.get_student_skill_tree(user_id, db)

@router.post("/code-doctor/diagnose", response_model=CodeDoctorResponse)
async def diagnose_code(req: CodeDoctorRequest, db: AsyncSession = Depends(get_db)):
    """Request Socratic AI Code Doctor diagnosis for a failed submission."""
    return await code_doctor_service.diagnose_submission(req.submission_id, db)
