from fastapi import APIRouter, Depends
from app.core.dashboard_auth import require_admin
from app.api.v1.endpoints.skill_config import router as skill_config_router
from app.api.v1.endpoints import student, teacher, admin, jobs, virtual_class, auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
admin_only = [Depends(require_admin)]
api_router.include_router(skill_config_router, prefix="/admin/skill-config", tags=["Skill configuration"], dependencies=admin_only)

api_router.include_router(student.router, prefix="/student", tags=["Student Features"], dependencies=admin_only)
api_router.include_router(teacher.router, prefix="/teacher", tags=["Teacher Features"], dependencies=admin_only)
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Features"], dependencies=admin_only)
api_router.include_router(virtual_class.router, prefix="/virtual-class", tags=["Virtual Class"], dependencies=admin_only)
api_router.include_router(jobs.router, prefix="/jobs", tags=["LLM Async Jobs"], dependencies=admin_only)
