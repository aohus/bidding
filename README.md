# 입찰 정보 시스템 (Bidding Notification System)

건설 입찰 공고를 검색하고 관리하는 멀티 유저 웹 애플리케이션입니다. 한국 정부의 나라장터 API를 활용하여 실시간 입찰 정보를 제공합니다.

## 📋 목차

- [시스템 아키텍처](#시스템-아키텍처)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [시작하기](#시작하기)
- [환경 변수 설정](#환경-변수-설정)
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
│                  프론트엔드 (React + shadcn-ui)              │
│  - 사용자 인증 UI                                            │
│  - 입찰 검색 폼                                              │
│  - 결과 테이블                                               │
│  - 사용자 설정 관리                                          │
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
└────────────┬───────────────────────┬────────────────────────┘
             │                       │
             ▼                       ▼
┌─────────────────────┐   ┌──────────────────────────────────┐
│  PostgreSQL DB      │   │   나라장터 API                    │
│  - 사용자 정보      │   │   (공공데이터포털)                │
│  - 검색 설정        │   │   - 입찰 공고 정보                │
│  - 북마크           │   │   - 문서 다운로드                 │
└─────────────────────┘   └──────────────────────────────────┘
```

### 주요 컴포넌트

1. **프론트엔드 (React + TypeScript)**
   - 위치: `/workspace/shadcn-ui/`
   - 포트: 5174 (개발), 4173 (프로덕션 프리뷰)
   - UI 프레임워크: shadcn-ui + Tailwind CSS
   - 상태 관리: React Hooks + localStorage (JWT)

2. **백엔드 (FastAPI + Python)**
   - 위치: `/workspace/backend/`
   - 포트: 8000
   - 비동기 처리: async/await
   - 데이터베이스: PostgreSQL (asyncpg)
   - 인증: JWT (python-jose)

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

## 🛠 기술 스택

### 프론트엔드
- **프레임워크**: React 18 + TypeScript
- **빌드 도구**: Vite
- **UI 라이브러리**: shadcn-ui, Tailwind CSS
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

## 🚀 시작하기

### 사전 요구사항

- **Node.js** 18+ 및 pnpm
- **Python** 3.10+
- **PostgreSQL** 14+
- **나라장터 API 키** ([공공데이터포털](https://www.data.go.kr)에서 발급)

### 1. 저장소 클론

```bash
cd /workspace
```

### 2. 백엔드 설정

#### 2.1 Python 가상환경 생성 및 의존성 설치

```bash
cd /workspace/backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 2.2 환경 변수 설정

`.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```env
# Database
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/bidding_db

# JWT Settings
SECRET_KEY=your-secret-key-here-generate-with-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys
NARAJANGTER_SERVICE_KEY=your-actual-service-key-from-data-go-kr

# CORS
FRONTEND_URL=http://localhost:5174
```

**SECRET_KEY 생성 방법:**
```bash
openssl rand -hex 32
```

#### 2.3 데이터베이스 설정

PostgreSQL 데이터베이스 생성:

```bash
psql -U postgres
CREATE DATABASE bidding_db;
\q
```

데이터베이스 마이그레이션 실행:

```bash
alembic upgrade head
```

#### 2.4 백엔드 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버 확인:
- API: http://localhost:8000
- 대화형 문서: http://localhost:8000/docs
- 대체 문서: http://localhost:8000/redoc

### 3. 프론트엔드 설정

새 터미널 열기:

```bash
cd /workspace/shadcn-ui
pnpm install
pnpm run dev
```

프론트엔드 접속: http://localhost:5174

## ⚙️ 환경 변수 설정

### 백엔드 환경 변수 (`/workspace/backend/.env`)

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql://user:pass@localhost:5432/bidding_db` |
| `SECRET_KEY` | JWT 서명 키 (32바이트 hex) | `09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7` |
| `ALGORITHM` | JWT 알고리즘 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 토큰 만료 시간 (분) | `30` |
| `NARAJANGTER_SERVICE_KEY` | 나라장터 API 서비스 키 | `your-key-from-data.go.kr` |
| `FRONTEND_URL` | 프론트엔드 URL (CORS) | `http://localhost:5174` |

### 프론트엔드 환경 변수

프론트엔드는 하드코딩된 백엔드 URL을 사용합니다 (`http://localhost:8000/api`). 프로덕션 배포 시 `/workspace/shadcn-ui/src/lib/backendApi.ts`와 `/workspace/shadcn-ui/src/lib/auth.ts`의 `API_BASE_URL`을 수정하세요.

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

### 4. 최적 입찰가 계산

1. 검색 결과에서 "계산" 버튼 클릭
2. 모달에서 입찰 정보 확인
3. 추정가격과 낙찰하한율 기반 최적가 확인
4. 필요시 입찰 문서 다운로드

### 5. 로그아웃

1. 헤더 우측 상단의 "로그아웃" 버튼 클릭
2. 로그인 화면으로 이동

## 🚢 배포 가이드

### 프로덕션 환경 준비

#### 1. 백엔드 배포

**환경 변수 설정:**
```env
DATABASE_URL=postgresql://user:password@prod-db-host:5432/bidding_db
SECRET_KEY=production-secret-key-32-bytes-hex
NARAJANGTER_SERVICE_KEY=production-service-key
FRONTEND_URL=https://your-frontend-domain.com
```

**Gunicorn으로 실행:**
```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Systemd 서비스 파일 (`/etc/systemd/system/bidding-api.service`):**
```ini
[Unit]
Description=Bidding Notification System API
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/bidding-backend
Environment="PATH=/opt/bidding-backend/venv/bin"
ExecStart=/opt/bidding-backend/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**서비스 시작:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable bidding-api
sudo systemctl start bidding-api
```

#### 2. 프론트엔드 배포

**환경 변수 업데이트:**

`/workspace/shadcn-ui/src/lib/backendApi.ts`와 `/workspace/shadcn-ui/src/lib/auth.ts`에서:
```typescript
const API_BASE_URL = 'https://api.your-domain.com/api';
```

**빌드:**
```bash
cd /workspace/shadcn-ui
pnpm run build
```

**Nginx 설정 (`/etc/nginx/sites-available/bidding-frontend`):**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /var/www/bidding-frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**배포:**
```bash
sudo cp -r dist/* /var/www/bidding-frontend/
sudo systemctl reload nginx
```

#### 3. HTTPS 설정 (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

#### 4. 데이터베이스 백업

**자동 백업 스크립트 (`/opt/scripts/backup-db.sh`):**
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U postgres bidding_db | gzip > "$BACKUP_DIR/bidding_db_$DATE.sql.gz"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
```

**Cron 작업 (매일 새벽 2시):**
```bash
0 2 * * * /opt/scripts/backup-db.sh
```

### 보안 체크리스트

- ✅ HTTPS 사용 (SSL/TLS 인증서)
- ✅ 강력한 SECRET_KEY 사용
- ✅ 데이터베이스 비밀번호 복잡도 확인
- ✅ 방화벽 설정 (필요한 포트만 개방)
- ✅ 정기적인 보안 업데이트
- ✅ 데이터베이스 정기 백업
- ✅ API 요청 속도 제한 (Rate Limiting)
- ✅ 로그 모니터링

### 모니터링

**Prometheus + Grafana 설정:**
```bash
# FastAPI에 prometheus-fastapi-instrumentator 추가
pip install prometheus-fastapi-instrumentator
```

`app/main.py`에 추가:
```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

## 🔧 문제 해결

### 백엔드 연결 실패

**증상:** 프론트엔드에서 "Failed to fetch" 에러

**해결:**
1. 백엔드 서버가 실행 중인지 확인: `curl http://localhost:8000/health`
2. CORS 설정 확인: `.env`의 `FRONTEND_URL` 확인
3. 방화벽 설정 확인

### 데이터베이스 연결 실패

**증상:** "Could not connect to database" 에러

**해결:**
1. PostgreSQL 서비스 상태 확인: `sudo systemctl status postgresql`
2. 데이터베이스 존재 확인: `psql -U postgres -l`
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
rm -rf node_modules pnpm-lock.yaml
pnpm install
pnpm run build
```

**백엔드:**
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

## 📞 지원

- **이슈 리포트**: GitHub Issues
- **문서**: `/workspace/backend/docs/`
- **API 문서**: http://localhost:8000/docs

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🙏 감사의 말

- [공공데이터포털](https://www.data.go.kr) - 나라장터 API 제공
- [FastAPI](https://fastapi.tiangolo.com/) - 백엔드 프레임워크
- [shadcn-ui](https://ui.shadcn.com/) - UI 컴포넌트