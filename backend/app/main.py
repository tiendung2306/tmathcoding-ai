from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.redis import init_redis_pool, close_redis_pool, get_redis_client
from app.core.job_manager import job_manager
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize Redis pool, recover orphaned jobs, start periodic sweeper
    await init_redis_pool()
    await job_manager.startup_recovery()
    job_manager.start_sweeper(interval_seconds=30)
    yield
    # Shutdown: stop sweeper and close Redis connections
    job_manager.stop_sweeper()
    await close_redis_pool()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Microservice API cho hệ thống tmath AI Diagnostic & Admin Dashboard.",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System"])
async def health_check():
    client = get_redis_client()
    redis_status = "connected" if client else "disconnected"
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "redis": redis_status,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
