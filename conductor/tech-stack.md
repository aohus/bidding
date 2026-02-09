# Tech Stack: 입찰 정보 시스템 (Bidding Notification System)

## 1. Back-end
- **Framework:** FastAPI (0.104.1+) - 고성능 비동기 API 서버
- **Language:** Python (3.10+)
- **ORM:** SQLAlchemy (2.0+) - 비동기 DB 연동 (async)
- **Database:** PostgreSQL + asyncpg (비동기 드라이버)
- **Migration:** Alembic - DB 스키마 버전 관리
- **Validation:** Pydantic (v2) - 데이터 모델링 및 유효성 검사
- **Security:** python-jose (JWT), passlib (bcrypt) - 인증 및 암호화
- **Client:** httpx - 비동기 외부 API(나라장터) 호출

## 2. Front-end
- **Library:** React (18/19) + TypeScript
- **Build Tool:** Vite - 빠른 개발 및 빌드 환경
- **Styling:** Tailwind CSS - 유틸리티 우선 CSS 프레임워크
- **UI Components:** shadcn/ui (Radix UI 기반) - 일관된 디자인 시스템
- **State Management:** React Hooks, Zustand (추정)
- **Data Fetching:** TanStack Query (React Query)
- **Routing:** React Router DOM

## 3. Infrastructure & DevOps
- **Containerization:** Docker & Docker Compose - 환경 일관성 유지
- **Web Server:** Nginx - 정적 파일 서빙 및 리버스 프록시
- **Database Server:** PostgreSQL (14+)
- **Email:** SMTP (Jinja2 템플릿 기반 HTML 메일 발송)
