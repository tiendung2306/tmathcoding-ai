from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "tmath AI Diagnostic & Admin Dashboard Service"
    API_V1_STR: str = "/api/v1"
    
    # Database MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_DB: str = "dmoj"
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # LLM Provider Configuration
    LLM_PROVIDER: str = "openai_compatible"  # 'openai_compatible' or 'gemini'
    LLM_BASE_URL: str = "http://localhost:11434/v1"  # Ollama endpoint
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "qwen2.5-coder:14b"
    
    # CORS Origins
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "*"]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
