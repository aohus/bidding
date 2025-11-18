# Bidding Notification System - Backend API

FastAPI-based backend for the construction bidding information system with async support.

## Features

- **Async API**: Built with FastAPI and async/await for high performance
- **User Authentication**: JWT-based authentication with secure password hashing
- **Database**: PostgreSQL with SQLAlchemy async ORM
- **API Integration**: Async calls to 나라장터 (NaraMarket) API
- **User Preferences**: Save and manage search preferences
- **Bookmarks**: Save favorite bid notices
- **CORS Support**: Configured for frontend integration

## Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL with asyncpg driver
- **ORM**: SQLAlchemy 2.0 (async)
- **Authentication**: python-jose (JWT), passlib (bcrypt)
- **HTTP Client**: httpx (async)
- **Migrations**: Alembic

## Setup

### 1. Install Dependencies

```bash
cd /workspace/backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/bidding_db
NARAMARKET_SERVICE_KEY=your_actual_service_key
SECRET_KEY=generate_a_secure_random_key
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
```

### 3. Initialize Database

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Run migrations
alembic upgrade head
```

### 4. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get access token
- `GET /api/auth/me` - Get current user info

### User Preferences
- `POST /api/preferences/` - Create/update default search preferences
- `GET /api/preferences/` - Get default search preferences
- `DELETE /api/preferences/` - Delete default search preferences
- `POST /api/preferences/searches` - Create saved search
- `GET /api/preferences/searches` - Get all saved searches
- `DELETE /api/preferences/searches/{search_id}` - Delete saved search

### Bid Notices
- `POST /api/bids/search` - Search bid notices (requires auth)
- `POST /api/bids/bookmarks` - Create bookmark
- `GET /api/bids/bookmarks` - Get all bookmarks
- `DELETE /api/bids/bookmarks/{bookmark_id}` - Delete bookmark

## Database Schema

See `/workspace/backend/docs/database_schema.md` for detailed schema documentation.

## Security

- Passwords are hashed using bcrypt
- JWT tokens expire after 30 minutes (configurable)
- All sensitive endpoints require authentication
- CORS is configured to allow only specified origins

## Development

### Generate New Migration

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Rollback Migration

```bash
alembic downgrade -1
```

## Production Deployment

1. Set strong `SECRET_KEY` in production
2. Use production-grade PostgreSQL database
3. Configure proper CORS origins
4. Use HTTPS for all communications
5. Set up proper logging and monitoring
6. Consider using Gunicorn with Uvicorn workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Testing

The API can be tested using:
- Interactive docs at `/docs`
- curl commands
- Postman or similar tools
- Frontend application

Example curl command:
```bash
# Register user
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"password123"}'

# Login
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```