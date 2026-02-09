# Email Notification System

이 문서는 입찰 정보 시스템의 이메일 알림 기능에 대한 설명입니다.

## 기능 개요

사용자가 저장한 검색 조건에 맞는 새로운 입찰 공고가 등록되면 자동으로 이메일 알림을 발송합니다.

## 주요 기능

### 1. 이메일 발송 서비스
- **위치**: `app/services/email_service.py`
- **지원 SMTP 서버**: Gmail, SendGrid, 기타 SMTP 서버
- **이메일 템플릿**: HTML 및 텍스트 형식 지원

### 2. 백그라운드 스케줄러
- **위치**: `app/services/scheduler.py`
- **기능**: 주기적으로 새로운 입찰 공고 확인 및 알림 발송
- **실행 주기**: 환경 변수로 설정 가능 (기본: 1시간)

### 3. 알림 설정 관리
- **위치**: `app/api/notifications.py`
- **엔드포인트**:
  - `GET /api/notifications/settings` - 알림 설정 조회
  - `PUT /api/notifications/settings` - 알림 설정 업데이트
  - `POST /api/notifications/test-email` - 테스트 이메일 발송

## 설정 방법

### 1. 환경 변수 설정

`.env` 파일에 다음 항목을 추가하세요:

```env
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
FROM_NAME=입찰 정보 시스템

# Notification Settings
ENABLE_EMAIL_NOTIFICATIONS=true
NOTIFICATION_CHECK_INTERVAL=3600
```

### 2. Gmail 설정

Gmail을 사용하는 경우:

1. Google 계정의 2단계 인증을 활성화합니다
2. 앱 비밀번호를 생성합니다: https://myaccount.google.com/apppasswords
3. 생성된 앱 비밀번호를 `SMTP_PASSWORD`에 입력합니다

### 3. SendGrid 설정

SendGrid를 사용하는 경우:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
FROM_EMAIL=your-verified-sender@yourdomain.com
```

## 알림 빈도 설정

사용자는 다음 세 가지 알림 빈도 중 하나를 선택할 수 있습니다:

- **realtime**: 1시간마다 확인
- **daily**: 하루에 한 번 (24시간마다)
- **weekly**: 일주일에 한 번 (7일마다)

## API 사용 예시

### 알림 설정 조회

```bash
curl -X GET "http://localhost:8000/api/notifications/settings" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**응답:**
```json
{
  "email_notifications_enabled": true,
  "notification_frequency": "daily",
  "last_notification_at": "2025-01-17T12:00:00Z"
}
```

### 알림 설정 업데이트

```bash
curl -X PUT "http://localhost:8000/api/notifications/settings" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email_notifications_enabled": true,
    "notification_frequency": "weekly"
  }'
```

### 테스트 이메일 발송

```bash
curl -X POST "http://localhost:8000/api/notifications/test-email" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 이메일 템플릿

### 템플릿 위치
- HTML 템플릿: `app/templates/email/*.html`
- 텍스트 템플릿: `app/templates/email/*.txt`

### 사용 가능한 템플릿

1. **bid_notification.html/txt**: 새로운 입찰 공고 알림
2. **welcome.html/txt**: 회원가입 환영 이메일

### 템플릿 커스터마이징

Jinja2 템플릿 엔진을 사용하므로 HTML/CSS를 수정하여 이메일 디자인을 변경할 수 있습니다.

## 데이터베이스 마이그레이션

이메일 알림 기능을 위해 `user_preferences` 테이블에 다음 필드가 추가되었습니다:

- `email_notifications_enabled` (Boolean): 이메일 알림 활성화 여부
- `notification_frequency` (String): 알림 빈도 (realtime/daily/weekly)
- `last_notification_at` (DateTime): 마지막 알림 발송 시간

마이그레이션 적용:
```bash
alembic upgrade head
```

## 문제 해결

### 이메일이 발송되지 않는 경우

1. **SMTP 설정 확인**
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`가 올바른지 확인
   - Gmail의 경우 앱 비밀번호를 사용하는지 확인

2. **방화벽 확인**
   - SMTP 포트 (587 또는 465)가 열려있는지 확인

3. **로그 확인**
   - 백엔드 콘솔에서 에러 메시지 확인

4. **테스트 이메일 발송**
   - `/api/notifications/test-email` 엔드포인트로 테스트

### 알림이 너무 자주 오는 경우

- `NOTIFICATION_CHECK_INTERVAL` 값을 증가시킵니다 (초 단위)
- 사용자의 `notification_frequency` 설정을 확인합니다

### 스케줄러가 시작되지 않는 경우

- `ENABLE_EMAIL_NOTIFICATIONS=true`로 설정되어 있는지 확인
- 백엔드 시작 로그에서 "Email notification scheduler started" 메시지 확인

## 보안 고려사항

1. **SMTP 비밀번호 보호**
   - `.env` 파일을 절대 Git에 커밋하지 마세요
   - 프로덕션 환경에서는 환경 변수로 관리하세요

2. **이메일 발송 제한**
   - 스팸으로 분류되지 않도록 발송 빈도를 적절히 조절하세요
   - Gmail은 하루 500통 제한이 있습니다

3. **사용자 이메일 검증**
   - 회원가입 시 이메일 인증을 구현하는 것을 권장합니다

## 향후 개선 사항

- [ ] 이메일 인증 기능 추가
- [ ] 이메일 발송 실패 재시도 로직
- [ ] 이메일 발송 통계 및 로그
- [ ] 사용자별 맞춤 이메일 템플릿
- [ ] 이메일 큐 시스템 (Celery, RQ 등)