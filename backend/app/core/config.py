import re
from typing import List, Optional
from urllib.parse import unquote

from pydantic_settings import BaseSettings

# data.go.kr '인코딩' 키의 특징: %XX 퍼센트 이스케이프를 포함한다.
# 인코딩 키를 그대로 serviceKey 로 보내면 이중 인코딩되어 HTTP 403 또는
# resultCode 30 이 된다. 반드시 '디코딩' 키를 써야 한다.
_PERCENT_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


def normalize_service_key(key: Optional[str]) -> str:
    """서비스키를 '디코딩' 형태로 정규화합니다.

    운영 .env 에 인코딩 키(96자, '%2B' 등 포함)가 들어있어 모든 호출이
    403 으로 실패한 사례가 있었다. 로드 시점에 방어적으로 되돌린다.
    퍼센트 이스케이프가 없는 키는 그대로 둔다 (리터럴 '%' 손상 방지).
    """
    if not key:
        return ""
    cleaned = key.strip()
    if _PERCENT_ESCAPE.search(cleaned):
        return unquote(cleaned)
    return cleaned


def build_key_pool(*keys: Optional[str]) -> List[str]:
    """서비스키 로테이션 풀을 구성합니다.

    - 빈 값 제거
    - 정규화 후 중복 제거 (인코딩/디코딩 사본이 같은 키로 합쳐진다)
    - 전달 순서 유지 (앞쪽이 우선 사용)
    """
    pool: List[str] = []
    for key in keys:
        normalized = normalize_service_key(key)
        if normalized and normalized not in pool:
            pool.append(normalized)
    return pool


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
    # 최후 폴백 키. 나라장터에서는 정상 동작하나 외부기관 6개 서비스에는
    # 활용신청이 안 돼 있어 403 이 난다 (403 도 로테이션 트리거이므로 안전).
    # 해당 계정으로 활용신청하면 코드 수정 없이 폴백이 살아난다.
    LOCAL_NARAJANGTER_SERVICE_KEY: str = ""

    # 전력개발포털(bigdata.kepco.co.kr)은 data.go.kr 이 아닌 별도 포털이라
    # 전용 키를 쓰고 파라미터명도 serviceKey 가 아니라 apiKey 다.
    ELECTRIC_INST_SERVICE_KEY: str = ""

    # 외부기관(비-나라장터) 공고 수집 스케줄러. 기본 비활성 — 배포 후 명시적으로 켠다.
    ENABLE_EXTERNAL_BID_SYNC: bool = False

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

    @property
    def data_go_kr_service_keys(self) -> List[str]:
        """data.go.kr 호출용 서비스키 로테이션 풀 (우선순위 순).

        나라장터와 외부기관 소스가 같은 풀을 공유한다 — 동일 계정의
        키이므로 한도도 함께 소진된다. 한 곳에서만 관리해 드리프트를 막는다.
        """
        return build_key_pool(
            self.NARAJANGTER_SERVICE_KEY,
            self.NARAJANGTER_SERVICE_KEY_V2,
            self.NARAJANGTER_SERVICE_KEY_V3,
            self.NARAJANGTER_SERVICE_KEY_V4,
            self.LOCAL_NARAJANGTER_SERVICE_KEY,
        )

    @property
    def electric_inst_api_key(self) -> str:
        """전력개발포털 전용 키 (정규화 적용)."""
        return normalize_service_key(self.ELECTRIC_INST_SERVICE_KEY)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()