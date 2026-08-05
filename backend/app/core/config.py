from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENV: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bidding_db"
    # SQLAlchemy echo. 운영에서 켜면 모든 SQL + 바인드 파라미터가 로그로 나간다.
    SQL_ECHO: bool = False

    # API Keys
    # 일일 호출 한도 초과 시 HTTP 429 → 다음 키로 자동 로테이션 (24h 후 V1 부터 재시도)
    NARAJANGTER_SERVICE_KEY: str
    NARAJANGTER_SERVICE_KEY_V2: str = ""
    NARAJANGTER_SERVICE_KEY_V3: str = ""
    NARAJANGTER_SERVICE_KEY_V4: str = ""
    
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
    ENABLE_BID_SYNC: bool = True
    ALERT_EMAIL: str = ""  # 동기화 실패 알림 수신 이메일 (미설정 시 FROM_EMAIL 사용)

    # Reserve-price one-shot backfill (배포 시 자동 실행)
    # 둘 다 비어있지 않을 때만 startup 시 1회 백필 + mv REFRESH 수행.
    # 완료 후 ON_DUPLICATE_SKIP 으로 동일 윈도우 재실행은 자동 skip 됨.
    RESERVE_PRICE_BACKFILL_FROM: str = ""  # YYYYMMDD
    RESERVE_PRICE_BACKFILL_TO: str = ""  # YYYYMMDD
    
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()