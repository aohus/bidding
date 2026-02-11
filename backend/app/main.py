from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api import auth, preferences, bids, notifications, locations, profile
from app.services.scheduler import notification_scheduler
from app.services.bid_sync_scheduler import bid_sync_scheduler
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup: Start the notification scheduler
    if settings.ENABLE_EMAIL_NOTIFICATIONS:
        asyncio.create_task(notification_scheduler.start())
        print("Email notification scheduler started")

    # Startup: Start bid data sync scheduler
    asyncio.create_task(bid_sync_scheduler.start())
    print("Bid data sync scheduler started")

    yield

    # Shutdown
    if settings.ENABLE_EMAIL_NOTIFICATIONS:
        await notification_scheduler.stop()
        print("Email notification scheduler stopped")

    await bid_sync_scheduler.stop()
    print("Bid data sync scheduler stopped")


app = FastAPI(
    title="Bidding Notification System API",
    description="Backend API for construction bidding information system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(preferences.router)
app.include_router(bids.router)
app.include_router(notifications.router)
app.include_router(locations.router)
app.include_router(profile.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Bidding Notification System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
