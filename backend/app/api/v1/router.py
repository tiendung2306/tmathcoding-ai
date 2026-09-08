from fastapi import APIRouter
from app.api.v1.endpoints import student, teacher, admin, jobs

api_router = APIRouter()

api_router.include_router(student.router, prefix="/student", tags=["Student Features"])
api_router.include_router(teacher.router, prefix="/teacher", tags=["Teacher Features"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Features"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["LLM Async Jobs"])
