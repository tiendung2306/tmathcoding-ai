from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
import os

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str = "/api/v1"
    
    # Backup Directory Configuration
    BACKUP_DIR: str = "backup"
    
    # Database MySQL Configuration (Required from Environment)
    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # LLM Provider Configuration
    LLM_PROVIDER: str = "openai_compatible"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "hf.co/empero-ai/Qwen3.8-4B-GGUF:Q4_K_M"

    # LLM Hyperparameters & Sampling Options
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    LLM_TOP_P: float = 0.95
    LLM_CONTEXT_WINDOW: int = 8192
    
    # CORS Origins
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
