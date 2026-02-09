# 입찰 정보 시스템 (Bidding Notification System)

건설 입찰 공고를 검색하고 관리하는 멀티 유저 웹 애플리케이션입니다. 한국 정부의 나라장터 API를 활용하여 실시간 입찰 정보를 제공합니다.

## 📋 목차

- [시스템 아키텍처](#시스템-아키텍처)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [시작하기](#시작하기)
  - [Docker로 시작하기 (권장)](#docker로-시작하기-권장)
  - [로컬 개발 환경](#로컬-개발-환경)
- [환경 변수 설정](#환경-변수-설정)
- [이메일 알림 설정](#이메일-알림-설정)
- [API 문서](#api-문서)
- [사용자 가이드](#사용자-가이드)
- [배포 가이드](#배포-가이드)
- [문제 해결](#문제-해결)

## 🏗 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                         사용자                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  프론트엔드 (React + frontend)              │
│  - 사용자 인증 UI                                            │
│  - 입찰 검색 폼                                              │
│  - 결과 테이블                                               │
│  - 사용자 설정 관리                                          │
│  - 알림 설정                                                 │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST API
                     │ (JWT 토큰 인증)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              백엔드 API (FastAPI + Python)                   │
│  - JWT 인증/인가                                             │
│  - 비즈니스 로직                                             │
│  - API 프록시                                                │
│  - 데이터 변환                                               │
│  - 이메일 알림 스케줄러 ⭐                                   │
└────────────┬───────────────────────┬────────────────────────┘
             │                       │
             ▼                       ▼
┌─────────────────────┐   ┌──────────────────────────────────┐
│  PostgreSQL DB      │   │   나라장터 API                    │
│  - 사용자 정보      │   │   (공공데이터포털)                │
│  - 검색 설정        │   │   - 입찰 공고 정보                │
│  - 북마크           │   │   - 문서 다운로드                 │
│  - 알림 설정 ⭐     │   └──────────────────────────────────┘
└─────────────────────┘
             │
             ▼
┌─────────────────────┐
│  SMTP 서버          │
│  (Gmail/SendGrid)   │
│  - 이메일 발송 ⭐   │
└─────────────────────┘
```

### 주요 컴포넌트

1. **프론트엔드 (React + TypeScript)**

   - 위치: `/workspace/frontend/`
   - 포트: 5174 (개발), 80 (Docker)
   - UI 프레임워크: frontend + Tailwind CSS
   - 상태 관리: React Hooks + localStorage (JWT)

2. **백엔드 (FastAPI + Python)**

   - 위치: `/workspace/backend/`
   - 포트: 8000
   - 비동기 처리: async/await
   - 데이터베이스: PostgreSQL (asyncpg)
   - 인증: JWT (python-jose)
   - 이메일: SMTP (Jinja2 템플릿)

3. **데이터베이스 (PostgreSQL)**
   - 5개 테이블: users, user_preferences, saved_searches, bid_notifications, user_bookmarks
   - 마이그레이션: Alembic

## ✨ 주요 기능

### 사용자 관리

- ✅ 회원가입 및 로그인 (JWT 인증)
- ✅ 비밀번호 암호화 (bcrypt)
- ✅ 사용자별 데이터 격리

### 입찰 검색

- ✅ 공고게시일시 또는 개찰일시 기준 검색
- ✅ 지역, 예산 범위 필터링
- ✅ 실시간 나라장터 API 연동 (비동기)

### 사용자 맞춤 기능

- ✅ 검색 조건 저장 및 자동 로드
- ✅ 여러 검색 조건 저장 (이름 지정)
- ✅ 관심 입찰 공고 북마크

### 입찰 분석

- ✅ 최적 입찰가 계산
- ✅ 낙찰 하한율 기반 추천
- ✅ 입찰 문서 다운로드

### 이메일 알림 ⭐ NEW

- ✅ 새로운 입찰 공고 자동 알림
- ✅ 알림 빈도 설정 (실시간/일일/주간)
- ✅ HTML 이메일 템플릿
- ✅ 백그라운드 스케줄러

## 🛠 기술 스택

### 프론트엔드

- **프레임워크**: React 18 + TypeScript
- **빌드 도구**: Vite
- **UI 라이브러리**: frontend, Tailwind CSS
- **HTTP 클라이언트**: Fetch API
- **라우팅**: React Router
- **알림**: Sonner (Toast)

### 백엔드

- **프레임워크**: FastAPI 0.109+
- **언어**: Python 3.10+
- **비동기 런타임**: uvicorn + asyncio
- **ORM**: SQLAlchemy 2.0 (async)
- **데이터베이스**: PostgreSQL + asyncpg
- **인증**: python-jose (JWT), passlib (bcrypt)
- **HTTP 클라이언트**: httpx (async)
- **마이그레이션**: Alembic
- **이메일**: SMTP + Jinja2 템플릿 ⭐

### 인프라

- **컨테이너**: Docker + Docker Compose
- **웹 서버**: Nginx (프론트엔드)
- **데이터베이스**: PostgreSQL 14

## 🚀 시작하기

### 사전 요구사항

**Docker 사용 시 (권장):**

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **나라장터 API 키** ([공공데이터포털](https://www.data.go.kr)에서 발급)
- **SMTP 계정** (Gmail 또는 SendGrid) - 이메일 알림 사용 시

**로컬 개발 시:**

- **Node.js** 18+ 및 pnpm
- **Python** 3.10+
- **PostgreSQL** 14+
- **나라장터 API 키**
- **SMTP 계정** - 이메일 알림 사용 시

### Docker로 시작하기 (권장)

Docker Compose를 사용하면 전체 스택을 한 번에 실행할 수 있습니다.

#### 1. 저장소 클론

```bash
cd /workspace
```

#### 2. 환경 변수 설정

`.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```env
# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=bidding_db
POSTGRES_PORT=5432

# Backend Configuration
BACKEND_PORT=8000
SECRET_KEY=generate_with_openssl_rand_hex_32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys
NARAJANGTER_SERVICE_KEY=your_actual_service_key_from_data_go_kr

# Frontend Configuration
FRONTEND_PORT=5174
FRONTEND_URL=http://localhost:5174

# Email Configuration (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
FROM_NAME=입찰 정보 시스템
ENABLE_EMAIL_NOTIFICATIONS=true
```

**SECRET_KEY 생성:**

```bash
openssl rand -hex 32
```

#### 3. Docker Compose로 실행

```bash
# 전체 스택 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그 확인
docker-compose logs -f backend
docker-compose logs -f frontend
```

#### 4. 접속 확인

- **프론트엔드**: http://localhost:5174
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

#### 5. Docker 관리 명령어

```bash
# 서비스 중지
docker-compose stop

# 서비스 재시작
docker-compose restart

# 서비스 중지 및 컨테이너 삭제
docker-compose down

# 볼륨까지 삭제 (데이터베이스 초기화)
docker-compose down -v

# 이미지 재빌드
docker-compose build --no-cache

# 특정 서비스만 재시작
docker-compose restart backend
```

### 로컬 개발 환경

Docker 없이 로컬에서 개발하는 경우:

#### 1. 백엔드 설정

```bash
cd /workspace/backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

환경 변수 설정 (`/workspace/backend/.env`)

백엔드 디렉토리의 `.env.example`을 복사하여 `.env` 파일을 생성하고 필요한 값을 입력하세요.

데이터베이스 설정:

```bash
# PostgreSQL 데이터베이스 생성
psql -U postgres
CREATE DATABASE bidding_db;
\q

# 마이그레이션 실행
alembic upgrade head
```

백엔드 서버 실행:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 프론트엔드 설정

새 터미널에서:

```bash
cd /workspace/frontend
pnpm install
pnpm run dev
```

프론트엔드 접속: http://localhost:5174

## ⚙️ 환경 변수 설정

### Docker Compose 환경 변수 (`/workspace/.env`)

| 변수명                        | 설명                       | 예시                       |
| ----------------------------- | -------------------------- | -------------------------- |
| `POSTGRES_USER`               | PostgreSQL 사용자명        | `postgres`                 |
| `POSTGRES_PASSWORD`           | PostgreSQL 비밀번호        | `your_secure_password`     |
| `POSTGRES_DB`                 | 데이터베이스 이름          | `bidding_db`               |
| `POSTGRES_PORT`               | PostgreSQL 포트            | `5432`                     |
| `BACKEND_PORT`                | 백엔드 API 포트            | `8000`                     |
| `SECRET_KEY`                  | JWT 서명 키 (32바이트 hex) | `openssl rand -hex 32`     |
| `ALGORITHM`                   | JWT 알고리즘               | `HS256`                    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 토큰 만료 시간 (분)        | `30`                       |
| `NARAJANGTER_SERVICE_KEY`     | 나라장터 API 서비스 키     | `your-key-from-data.go.kr` |
| `FRONTEND_PORT`               | 프론트엔드 포트            | `5174`                     |
| `FRONTEND_URL`                | 프론트엔드 URL (CORS)      | `http://localhost:5174`    |
| `SMTP_HOST`                   | SMTP 서버 주소             | `smtp.gmail.com`           |
| `SMTP_PORT`                   | SMTP 포트                  | `587`                      |
| `SMTP_USER`                   | SMTP 사용자명              | `your-email@gmail.com`     |
| `SMTP_PASSWORD`               | SMTP 비밀번호              | `your-app-password`        |
| `FROM_EMAIL`                  | 발신 이메일 주소           | `your-email@gmail.com`     |
| `FROM_NAME`                   | 발신자 이름                | `입찰 정보 시스템`         |
| `ENABLE_EMAIL_NOTIFICATIONS`  | 이메일 알림 활성화         | `true`                     |

## 📧 이메일 알림 설정

### Gmail 설정

1. Google 계정의 2단계 인증을 활성화합니다
2. 앱 비밀번호를 생성합니다: https://myaccount.google.com/apppasswords
3. 생성된 앱 비밀번호를 `SMTP_PASSWORD`에 입력합니다

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=generated-app-password
FROM_EMAIL=your-email@gmail.com
```

### SendGrid 설정

1. SendGrid 계정 생성 및 API 키 발급
2. 발신자 이메일 인증

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
FROM_EMAIL=your-verified-sender@yourdomain.com
```

### 알림 빈도 설정

사용자는 다음 세 가지 알림 빈도 중 하나를 선택할 수 있습니다:

- **realtime**: 1시간마다 확인
- **daily**: 하루에 한 번 (24시간마다)
- **weekly**: 일주일에 한 번 (7일마다)

상세한 이메일 알림 설정 가이드는 [backend/README_EMAIL.md](backend/README_EMAIL.md)를 참조하세요.

## 📚 API 문서

### 인증 엔드포인트

#### POST /api/auth/register

사용자 회원가입

**요청 본문:**

```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```

**응답:**

```json
{
  "user_id": "uuid",
  "username": "testuser",
  "email": "test@example.com",
  "created_at": "2025-01-17T12:00:00Z"
}
```

#### POST /api/auth/login

사용자 로그인

**요청 본문 (form-data):**

```
username=testuser
password=password123
```

**응답:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### GET /api/auth/me

현재 사용자 정보 조회 (인증 필요)

**헤더:**

```
Authorization: Bearer {access_token}
```

**응답:**

```json
{
  "user_id": "uuid",
  "username": "testuser",
  "email": "test@example.com",
  "created_at": "2025-01-17T12:00:00Z"
}
```

### 알림 설정 엔드포인트 ⭐ NEW

#### GET /api/notifications/settings

알림 설정 조회 (인증 필요)

**응답:**

```json
{
  "email_notifications_enabled": true,
  "notification_frequency": "daily",
  "last_notification_at": "2025-01-17T12:00:00Z"
}
```

#### PUT /api/notifications/settings

알림 설정 업데이트 (인증 필요)

**요청 본문:**

```json
{
  "email_notifications_enabled": true,
  "notification_frequency": "weekly"
}
```

#### POST /api/notifications/test-email

테스트 이메일 발송 (인증 필요)

**응답:**

```json
{
  "message": "Test email will be sent to user@example.com",
  "status": "queued"
}
```

### 사용자 설정 엔드포인트

#### POST /api/preferences

검색 조건 저장/업데이트 (인증 필요)

**요청 본문:**

```json
{
  "search_conditions": {
    "inqryDiv": "1",
    "startDate": "2025-01-01",
    "endDate": "2025-01-31",
    "region": "11"
  }
}
```

#### GET /api/preferences

저장된 검색 조건 조회 (인증 필요)

**응답:**

```json
{
  "preference_id": "uuid",
  "user_id": "uuid",
  "search_conditions": { ... },
  "created_at": "2025-01-17T12:00:00Z",
  "updated_at": "2025-01-17T12:00:00Z"
}
```

### 입찰 검색 엔드포인트

#### POST /api/bids/search

입찰 공고 검색 (인증 필요)

**요청 본문:**

```json
{
  "inqry_div": "1",
  "inqry_bgn_dt": "202501010000",
  "inqry_end_dt": "202501310000",
  "prtcpt_lmt_rgn_cd": "11",
  "num_of_rows": 100,
  "page_no": 1
}
```

**응답:**

```json
{
  "items": [
    {
      "bidNtceNo": "20250117001",
      "bidNtceNm": "도로 건설 공사",
      "ntceInsttNm": "서울시",
      "presmptPrce": "1000000000",
      ...
    }
  ],
  "total_count": 150,
  "page_no": 1,
  "num_of_rows": 100
}
```

### 저장된 검색 엔드포인트

#### POST /api/saved-searches

검색 조건 저장 (인증 필요)

**요청 본문:**

```json
{
  "search_name": "서울 도로 공사",
  "filters": {
    "inqryDiv": "1",
    "region": "11",
    "presmptPrceBgn": "100000000"
  }
}
```

#### GET /api/saved-searches

저장된 검색 목록 조회 (인증 필요)

#### DELETE /api/saved-searches/{search_id}

저장된 검색 삭제 (인증 필요)

### 북마크 엔드포인트

#### POST /api/bookmarks

북마크 추가 (인증 필요)

**요청 본문:**

```json
{
  "bid_notice_no": "20250117001",
  "bid_notice_name": "도로 건설 공사",
  "notes": "관심 입찰 공고"
}
```

#### GET /api/bookmarks

북마크 목록 조회 (인증 필요)

#### DELETE /api/bookmarks/{bookmark_id}

북마크 삭제 (인증 필요)

## 📖 사용자 가이드

### 1. 회원가입 및 로그인

1. 애플리케이션 접속 (http://localhost:5174)
2. "회원가입" 탭 선택
3. 사용자명, 이메일, 비밀번호 입력
4. "회원가입" 버튼 클릭
5. "로그인" 탭으로 전환
6. 사용자명과 비밀번호로 로그인

### 2. 입찰 공고 검색

1. 로그인 후 메인 화면에서 검색 폼 확인
2. 조회 구분 선택 (공고게시일시 또는 개찰일시)
3. 시작일과 종료일 입력
4. 선택사항: 지역 코드 입력 (예: 11 = 서울)
5. "검색" 버튼 클릭
6. 검색 결과 테이블에서 입찰 공고 확인

### 3. 검색 조건 저장

1. 검색 폼에서 원하는 조건 입력
2. "조건 저장" 버튼 클릭
3. 다음 로그인 시 저장된 조건이 자동으로 로드됨

### 4. 이메일 알림 설정 ⭐

1. 설정 페이지로 이동
2. "이메일 알림 활성화" 토글
3. 알림 빈도 선택 (실시간/일일/주간)
4. "저장" 버튼 클릭
5. 새로운 입찰 공고가 등록되면 자동으로 이메일 수신

### 5. 최적 입찰가 계산

1. 검색 결과에서 "계산" 버튼 클릭
2. 모달에서 입찰 정보 확인
3. 추정가격과 낙찰하한율 기반 최적가 확인
4. 필요시 입찰 문서 다운로드

### 6. 로그아웃

1. 헤더 우측 상단의 "로그아웃" 버튼 클릭
2. 로그인 화면으로 이동

## 🚢 배포 가이드

상세한 프로덕션 배포 가이드는 [DEPLOYMENT.md](DEPLOYMENT.md)를 참조하세요.

### Docker를 사용한 프로덕션 배포

#### 1. 환경 변수 설정

프로덕션 `.env` 파일:

```env
POSTGRES_USER=bidding_user
POSTGRES_PASSWORD=STRONG_PRODUCTION_PASSWORD
POSTGRES_DB=bidding_db
SECRET_KEY=PRODUCTION_SECRET_KEY_32_BYTES_HEX
NARAJANGTER_SERVICE_KEY=PRODUCTION_SERVICE_KEY
FRONTEND_URL=https://yourdomain.com

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
ENABLE_EMAIL_NOTIFICATIONS=true
```

#### 2. Docker Compose로 배포

```bash
# 프로덕션 모드로 빌드
docker-compose -f docker-compose.yml build

# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

#### 3. Nginx 리버스 프록시 설정

프로덕션 환경에서는 Nginx를 리버스 프록시로 사용하여 SSL/TLS를 설정합니다.

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5174;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 4. SSL 인증서 발급

```bash
sudo certbot --nginx -d yourdomain.com
```

## 🔧 문제 해결

### Docker 관련 문제

#### 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker-compose logs

# 특정 서비스 로그
docker-compose logs backend

# 컨테이너 상태 확인
docker-compose ps
```

#### 데이터베이스 연결 실패

```bash
# PostgreSQL 컨테이너 상태 확인
docker-compose ps postgres

# PostgreSQL 로그 확인
docker-compose logs postgres

# 데이터베이스 재시작
docker-compose restart postgres
```

#### 포트 충돌

```bash
# 사용 중인 포트 확인
sudo lsof -i :8000
sudo lsof -i :5174
sudo lsof -i :5432

# .env 파일에서 포트 변경
BACKEND_PORT=8001
FRONTEND_PORT=5175
POSTGRES_PORT=5433
```

### 이메일 알림 문제

#### 이메일이 발송되지 않음

1. SMTP 설정 확인 (`.env` 파일)
2. Gmail의 경우 앱 비밀번호 사용 확인
3. 방화벽에서 SMTP 포트 (587) 개방 확인
4. 백엔드 로그에서 에러 메시지 확인

```bash
docker-compose logs backend | grep -i email
```

5. 테스트 이메일 발송으로 확인

```bash
curl -X POST "http://localhost:8000/api/notifications/test-email" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### 알림 스케줄러가 작동하지 않음

1. `ENABLE_EMAIL_NOTIFICATIONS=true` 설정 확인
2. 백엔드 시작 로그에서 "Email notification scheduler started" 메시지 확인
3. 사용자의 알림 설정이 활성화되어 있는지 확인

### 백엔드 연결 실패

**증상:** 프론트엔드에서 "Failed to fetch" 에러

**해결:**

1. 백엔드 서버가 실행 중인지 확인: `curl http://localhost:8000/health`
2. CORS 설정 확인: `.env`의 `FRONTEND_URL` 확인
3. 방화벽 설정 확인

### 데이터베이스 연결 실패

**증상:** "Could not connect to database" 에러

**해결:**

1. PostgreSQL 서비스 상태 확인: `docker-compose ps postgres`
2. 데이터베이스 존재 확인: `docker-compose exec postgres psql -U postgres -l`
3. `.env`의 `DATABASE_URL` 확인
4. 네트워크 연결 확인

### JWT 토큰 만료

**증상:** "Could not validate credentials" 에러

**해결:**

1. 로그아웃 후 다시 로그인
2. `ACCESS_TOKEN_EXPIRE_MINUTES` 값 조정 (`.env`)

### 나라장터 API 오류

**증상:** "API Error: ..." 메시지

**해결:**

1. ServiceKey 유효성 확인
2. API 호출 제한 확인 (일일 트래픽 제한)
3. 요청 파라미터 형식 확인

### 빌드 오류

**프론트엔드:**

```bash
docker-compose build --no-cache frontend
```

**백엔드:**

```bash
docker-compose build --no-cache backend
```

## 📞 지원

- **이슈 리포트**: GitHub Issues
- **문서**: `/workspace/backend/docs/`
- **API 문서**: http://localhost:8000/docs
- **이메일 알림 가이드**: [backend/README_EMAIL.md](backend/README_EMAIL.md)

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🙏 감사의 말

- [공공데이터포털](https://www.data.go.kr) - 나라장터 API 제공
- [FastAPI](https://fastapi.tiangolo.com/) - 백엔드 프레임워크
- [frontend](https://ui.shadcn.com/) - UI 컴포넌트
- [Docker](https://www.docker.com/) - 컨테이너화 플랫폼
