"""Source database settings used only by offline operator tools."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class OfflineSourceSettings(BaseSettings):
    SOURCE_DB_HOST: str
    SOURCE_DB_PORT: int = Field(default=3306, ge=1, le=65535)
    SOURCE_DB_USER: str
    SOURCE_DB_PASSWORD: str
    SOURCE_DB_NAME: str

    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.SOURCE_DB_USER,
            password=self.SOURCE_DB_PASSWORD,
            host=self.SOURCE_DB_HOST,
            port=self.SOURCE_DB_PORT,
            database=self.SOURCE_DB_NAME,
            query={"charset": "utf8mb4"},
        )
