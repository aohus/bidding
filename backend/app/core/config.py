from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bidding_db"
    
    # API Keys
    NARAJANGTER_SERVICE_KEY: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5432,http://localhost:8009"
    
    # Email Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    FROM_NAME: str = "입찰 정보 시스템"
    
    # Notification Settings
    ENABLE_EMAIL_NOTIFICATIONS: bool = True
    NOTIFICATION_CHECK_INTERVAL: int = 3600  # seconds (1 hour)
    
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()