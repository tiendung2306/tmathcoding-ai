from fastapi import APIRouter
from app.api.v1.endpoints.skill_config import router as skill_config_router
from app.api.v1.endpoints import student, teacher, admin, jobs, virtual_class

api_router = APIRouter()
api_router.include_router(skill_config_router, prefix="/admin/skill-config", tags=["Skill configuration"])

api_router.include_router(student.router, prefix="/student", tags=["Student Features"])
api_router.include_router(teacher.router, prefix="/teacher", tags=["Teacher Features"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Features"])
api_router.include_router(virtual_class.router, prefix="/virtual-class", tags=["Virtual Class"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["LLM Async Jobs"])
