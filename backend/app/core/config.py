from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator
from sqlalchemy.engine import URL
from typing import List, Union
import json
import os

class Settings(BaseSettings):
    PROJECT_NAME: str
    API_V1_STR: str = "/api/v1"
    DASHBOARD_ADMIN_PROFILE_ID: int = Field(default=2, ge=1)
    SOURCE_API_BASE_URL: str = ""
    SOURCE_API_TOKEN: str = ""
    SOURCE_API_TIMEOUT_SECONDS: float = Field(default=8.0, gt=0)
    
    # Dashboard-owned database. Source data is accessed only through SOURCE_API_*.
    DASHBOARD_DB_HOST: str
    DASHBOARD_DB_PORT: int = Field(default=3306, ge=1, le=65535)
    DASHBOARD_DB_USER: str
    DASHBOARD_DB_PASSWORD: str
    DASHBOARD_DB_NAME: str = Field(default="tmath_dashboard", pattern=r"^[A-Za-z0-9_]{1,64}$", validation_alias=AliasChoices("DASHBOARD_DB_NAME", "CONFIG_MYSQL_DB"))
    DASHBOARD_MIGRATION_USER: str = ""
    DASHBOARD_MIGRATION_PASSWORD: str = ""
    AUTH_COOKIE_SECURE: bool = True

    @property
    def dashboard_database_url(self) -> URL:
        return URL.create("mysql+aiomysql", username=self.DASHBOARD_DB_USER, password=self.DASHBOARD_DB_PASSWORD,
                          host=self.DASHBOARD_DB_HOST, port=self.DASHBOARD_DB_PORT, database=self.DASHBOARD_DB_NAME,
                          query={"charset": "utf8mb4"})

    @property
    def dashboard_migration_url(self) -> URL:
        if not self.DASHBOARD_MIGRATION_USER or not self.DASHBOARD_MIGRATION_PASSWORD:
            raise ValueError("Migration requires DASHBOARD_MIGRATION_USER and DASHBOARD_MIGRATION_PASSWORD")
        return self.dashboard_database_url.set(drivername="mysql+pymysql", username=self.DASHBOARD_MIGRATION_USER,
                                               password=self.DASHBOARD_MIGRATION_PASSWORD)

    CONFIG_MYSQL_DB = property(lambda self: self.DASHBOARD_DB_NAME)

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
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(default=240.0, gt=0, allow_inf_nan=False)
    
    # CORS Origins
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def sanitize_cors_origins(cls, v):
        """Parses CORS origins from env (JSON list or comma-separated string)
        and strips wildcard '*' to keep CORS valid with allow_credentials=True."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                v = json.loads(v)
            else:
                v = [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            v = [origin for origin in v if origin and origin != "*"]
        return v or ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
