# 배포 가이드 (Deployment Guide)

이 문서는 입찰 정보 시스템을 프로덕션 환경에 배포하는 상세 가이드입니다.

## 목차

1. [배포 아키텍처](#배포-아키텍처)
2. [사전 준비](#사전-준비)
3. [백엔드 배포](#백엔드-배포)
4. [프론트엔드 배포](#프론트엔드-배포)
5. [데이터베이스 설정](#데이터베이스-설정)
6. [리버스 프록시 설정](#리버스-프록시-설정)
7. [SSL/TLS 설정](#ssltls-설정)
8. [모니터링 및 로깅](#모니터링-및-로깅)
9. [백업 및 복구](#백업-및-복구)
10. [성능 최적화](#성능-최적화)

## 배포 아키텍처

```
Internet
    │
    ▼
┌─────────────────────────────────────┐
│   Load Balancer (Optional)          │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Nginx (Reverse Proxy + SSL)       │
│   - Frontend (Static Files)         │
│   - Backend API Proxy               │
└────────┬───────────────┬────────────┘
         │               │
         ▼               ▼
┌──────────────┐  ┌──────────────────┐
│  Frontend    │  │  Backend API     │
│  (Static)    │  │  (Gunicorn +     │
│              │  │   Uvicorn)       │
└──────────────┘  └────────┬─────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  PostgreSQL     │
                  │  (Primary +     │
                  │   Replica)      │
                  └─────────────────┘
```

## 사전 준비

### 1. 서버 요구사항

**최소 사양:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 50GB SSD
- OS: Ubuntu 22.04 LTS 또는 CentOS 8+

**권장 사양:**
- CPU: 4 cores
- RAM: 8GB
- Storage: 100GB SSD

### 2. 도메인 및 DNS 설정

```
A Record: api.yourdomain.com → Server IP
A Record: yourdomain.com → Server IP
```

### 3. 방화벽 설정

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# FirewallD (CentOS)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 백엔드 배포

### 1. 시스템 패키지 설치

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip postgresql postgresql-contrib nginx

# CentOS/RHEL
sudo dnf install -y python3.10 python3-pip postgresql-server postgresql-contrib nginx
```

### 2. 애플리케이션 디렉토리 생성

```bash
sudo mkdir -p /opt/bidding-backend
sudo chown $USER:$USER /opt/bidding-backend
```

### 3. 코드 배포

```bash
cd /opt/bidding-backend
git clone <your-repo-url> .
# 또는 rsync로 파일 복사
rsync -avz /workspace/backend/ /opt/bidding-backend/
```

### 4. Python 가상환경 설정

```bash
cd /opt/bidding-backend
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 5. 환경 변수 설정

```bash
sudo nano /opt/bidding-backend/.env
```

프로덕션 환경 변수:

```env
# Database
DATABASE_URL=postgresql://bidding_user:STRONG_PASSWORD@localhost:5432/bidding_db

# JWT Settings
SECRET_KEY=GENERATE_WITH_openssl_rand_hex_32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys
NARAJANGTER_SERVICE_KEY=YOUR_PRODUCTION_SERVICE_KEY

# CORS
FRONTEND_URL=https://yourdomain.com
```

### 6. Systemd 서비스 생성

```bash
sudo nano /etc/systemd/system/bidding-api.service
```

서비스 파일 내용:

```ini
[Unit]
Description=Bidding Notification System API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/bidding-backend
Environment="PATH=/opt/bidding-backend/venv/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/bidding-backend/venv/bin/gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/bidding-api/access.log \
    --error-logfile /var/log/bidding-api/error.log \
    --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7. 로그 디렉토리 생성

```bash
sudo mkdir -p /var/log/bidding-api
sudo chown www-data:www-data /var/log/bidding-api
```

### 8. 서비스 시작

```bash
sudo systemctl daemon-reload
sudo systemctl enable bidding-api
sudo systemctl start bidding-api
sudo systemctl status bidding-api
```

### 9. 서비스 확인

```bash
curl http://127.0.0.1:8000/health
# 응답: {"status":"healthy"}
```

## 프론트엔드 배포

### 1. 빌드 환경 설정

로컬 또는 CI/CD 환경에서:

```bash
cd /workspace/shadcn-ui

# API URL 업데이트
sed -i "s|http://localhost:8000/api|https://api.yourdomain.com/api|g" src/lib/backendApi.ts
sed -i "s|http://localhost:8000/api|https://api.yourdomain.com/api|g" src/lib/auth.ts

# 빌드
pnpm install
pnpm run build
```

### 2. 빌드 파일 배포

```bash
# 서버에 디렉토리 생성
sudo mkdir -p /var/www/bidding-frontend
sudo chown www-data:www-data /var/www/bidding-frontend

# 빌드 파일 복사
rsync -avz dist/ user@server:/var/www/bidding-frontend/
```

## 데이터베이스 설정

### 1. PostgreSQL 초기화 (CentOS만)

```bash
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 2. 데이터베이스 및 사용자 생성

```bash
sudo -u postgres psql
```

SQL 명령:

```sql
-- 사용자 생성
CREATE USER bidding_user WITH PASSWORD 'STRONG_PASSWORD';

-- 데이터베이스 생성
CREATE DATABASE bidding_db OWNER bidding_user;

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE bidding_db TO bidding_user;

-- 연결 및 확인
\c bidding_db
\q
```

### 3. PostgreSQL 설정 최적화

`/var/lib/pgsql/data/postgresql.conf` (CentOS) 또는 `/etc/postgresql/14/main/postgresql.conf` (Ubuntu):

```conf
# 메모리 설정 (8GB RAM 기준)
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 32MB

# 연결 설정
max_connections = 100

# WAL 설정
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# 쿼리 플래너
random_page_cost = 1.1  # SSD 사용 시
effective_io_concurrency = 200
```

재시작:

```bash
sudo systemctl restart postgresql
```

### 4. 데이터베이스 마이그레이션

```bash
cd /opt/bidding-backend
source venv/bin/activate
alembic upgrade head
```

### 5. 데이터베이스 접근 제한

`/var/lib/pgsql/data/pg_hba.conf` 또는 `/etc/postgresql/14/main/pg_hba.conf`:

```conf
# 로컬 연결만 허용
local   all             all                                     peer
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
```

## 리버스 프록시 설정

### Nginx 설정

```bash
sudo nano /etc/nginx/sites-available/bidding-system
```

설정 파일:

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

# Upstream
upstream backend_api {
    server 127.0.0.1:8000 fail_timeout=10s max_fails=3;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# Frontend
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com;

    # SSL certificates (will be added by certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    root /var/www/bidding-frontend;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api {
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://backend_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Auth endpoints with stricter rate limiting
    location /api/auth {
        limit_req zone=auth_limit burst=5 nodelay;
        
        proxy_pass http://backend_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Backend API (optional separate domain)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://backend_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

활성화:

```bash
sudo ln -s /etc/nginx/sites-available/bidding-system /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## SSL/TLS 설정

### Let's Encrypt 인증서 발급

```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx  # Ubuntu
sudo dnf install certbot python3-certbot-nginx  # CentOS

# 인증서 발급
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com

# 자동 갱신 테스트
sudo certbot renew --dry-run
```

### 자동 갱신 설정

Certbot은 자동으로 systemd timer를 설정합니다. 확인:

```bash
sudo systemctl status certbot.timer
```

## 모니터링 및 로깅

### 1. 로그 로테이션

```bash
sudo nano /etc/logrotate.d/bidding-api
```

내용:

```
/var/log/bidding-api/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    sharedscripts
    postrotate
        systemctl reload bidding-api > /dev/null 2>&1 || true
    endscript
}
```

### 2. Prometheus 메트릭 (선택사항)

`requirements.txt`에 추가:

```
prometheus-fastapi-instrumentator==6.1.0
```

`app/main.py` 수정:

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(...)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

### 3. 헬스체크 스크립트

```bash
sudo nano /opt/scripts/health-check.sh
```

내용:

```bash
#!/bin/bash

API_URL="http://127.0.0.1:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)

if [ $RESPONSE -ne 200 ]; then
    echo "API health check failed: HTTP $RESPONSE"
    systemctl restart bidding-api
    echo "Service restarted at $(date)" >> /var/log/bidding-api/restart.log
fi
```

Cron 작업:

```bash
*/5 * * * * /opt/scripts/health-check.sh
```

## 백업 및 복구

### 1. 데이터베이스 백업 스크립트

```bash
sudo mkdir -p /opt/backups/postgres
sudo nano /opt/scripts/backup-db.sh
```

내용:

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="bidding_db"
DB_USER="bidding_user"

# 백업 실행
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > "$BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz"

# 7일 이상 된 백업 삭제
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

# 백업 성공 로그
echo "Backup completed: ${DB_NAME}_${DATE}.sql.gz" >> /var/log/backup.log
```

권한 설정:

```bash
sudo chmod +x /opt/scripts/backup-db.sh
```

Cron 작업 (매일 새벽 2시):

```bash
0 2 * * * /opt/scripts/backup-db.sh
```

### 2. 복구 절차

```bash
# 백업 파일 압축 해제
gunzip /opt/backups/postgres/bidding_db_20250117_020000.sql.gz

# 데이터베이스 복구
sudo -u postgres psql -d bidding_db < /opt/backups/postgres/bidding_db_20250117_020000.sql
```

### 3. 원격 백업 (S3/Object Storage)

```bash
# AWS CLI 설치
sudo apt install awscli

# S3 업로드 스크립트
aws s3 cp "$BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz" s3://your-bucket/backups/
```

## 성능 최적화

### 1. 데이터베이스 인덱스

```sql
-- 자주 조회되는 컬럼에 인덱스 생성
CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX idx_saved_searches_user_id ON saved_searches(user_id);
CREATE INDEX idx_bookmarks_user_id ON user_bookmarks(user_id);
CREATE INDEX idx_bookmarks_bid_notice ON user_bookmarks(bid_notice_no);
```

### 2. 연결 풀링

`app/db/database.py`:

```python
engine = create_async_engine(
    database_url,
    echo=False,  # 프로덕션에서는 False
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### 3. Redis 캐싱 (선택사항)

```bash
sudo apt install redis-server
pip install redis aioredis
```

캐시 레이어 추가:

```python
import aioredis

redis = await aioredis.create_redis_pool('redis://localhost')

# 캐시 사용 예시
cached_data = await redis.get('bid_search_key')
if not cached_data:
    data = await fetch_from_api()
    await redis.setex('bid_search_key', 300, json.dumps(data))
```

### 4. CDN 사용 (선택사항)

정적 파일을 CloudFlare, AWS CloudFront 등의 CDN에 배포하여 로딩 속도 향상.

## 보안 체크리스트

- [ ] HTTPS 활성화 (Let's Encrypt)
- [ ] 강력한 SECRET_KEY 사용 (32바이트 hex)
- [ ] 데이터베이스 비밀번호 복잡도 확인
- [ ] 방화벽 설정 (필요한 포트만 개방)
- [ ] SSH 키 기반 인증 사용
- [ ] 정기적인 보안 업데이트 (`sudo apt update && sudo apt upgrade`)
- [ ] Rate limiting 설정 (Nginx)
- [ ] CORS 설정 확인
- [ ] SQL Injection 방지 (SQLAlchemy ORM 사용)
- [ ] XSS 방지 (React 기본 보호)
- [ ] 로그 모니터링 및 알림 설정
- [ ] 정기 백업 자동화
- [ ] 비상 복구 계획 수립

## 트러블슈팅

### 서비스 재시작

```bash
# 백엔드
sudo systemctl restart bidding-api

# Nginx
sudo systemctl reload nginx

# PostgreSQL
sudo systemctl restart postgresql
```

### 로그 확인

```bash
# 백엔드 로그
sudo journalctl -u bidding-api -f

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# PostgreSQL 로그
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

### 성능 모니터링

```bash
# 시스템 리소스
htop

# 네트워크 연결
sudo netstat -tulpn | grep LISTEN

# 디스크 사용량
df -h

# 프로세스 확인
ps aux | grep gunicorn
```

## 결론

이 가이드를 따라 입찰 정보 시스템을 안전하고 확장 가능한 프로덕션 환경에 배포할 수 있습니다. 정기적인 모니터링, 백업, 보안 업데이트를 통해 시스템의 안정성을 유지하세요.