from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api import auth, preferences, bids, notifications, locations, profile, estimate_rate, external_bids
from app.services.scheduler import notification_scheduler
from app.services.bid_sync_scheduler import bid_sync_scheduler
from app.services.external_bid_sync_scheduler import external_bid_sync_scheduler
import asyncio
import logging

logger = logging.getLogger(__name__)

is_production = settings.ENV == "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup: Start the notification scheduler
    if settings.ENABLE_EMAIL_NOTIFICATIONS:
        asyncio.create_task(notification_scheduler.start())
        logger.info("Email notification scheduler started")

    # Startup: Start bid data sync scheduler
    if settings.ENABLE_BID_SYNC:
        asyncio.create_task(bid_sync_scheduler.start())
        logger.info("Bid data sync scheduler started")

    # Startup: 외부기관(비-나라장터) 공고 수집 스케줄러.
    # 나라장터 스케줄러와 독립 — 기본 비활성이며 마이그레이션 적용 후 켠다.
    if settings.ENABLE_EXTERNAL_BID_SYNC:
        asyncio.create_task(external_bid_sync_scheduler.start())
        logger.info("External bid sync scheduler started")

    # Startup: One-shot reserve_price backfill (env-driven)
    if settings.RESERVE_PRICE_BACKFILL_FROM and settings.RESERVE_PRICE_BACKFILL_TO:
        from app.services.reserve_price_backfill import backfill_reserve_prices

        async def _run_backfill() -> None:
            try:
                logger.info(
                    f"Starting one-shot reserve_price backfill: "
                    f"{settings.RESERVE_PRICE_BACKFILL_FROM} ~ {settings.RESERVE_PRICE_BACKFILL_TO}"
                )
                await backfill_reserve_prices(
                    settings.RESERVE_PRICE_BACKFILL_FROM,
                    settings.RESERVE_PRICE_BACKFILL_TO,
                )
            except Exception as exc:  # background task: must not crash startup
                logger.error(f"reserve_price startup backfill failed: {exc}")

        asyncio.create_task(_run_backfill())

    yield

    # Shutdown
    if settings.ENABLE_EMAIL_NOTIFICATIONS:
        await notification_scheduler.stop()
        logger.info("Email notification scheduler stopped")

    if settings.ENABLE_BID_SYNC:
        await bid_sync_scheduler.stop()
        logger.info("Bid data sync scheduler stopped")

    if settings.ENABLE_EXTERNAL_BID_SYNC:
        await external_bid_sync_scheduler.stop()
        logger.info("External bid sync scheduler stopped")


app = FastAPI(
    title="Bidding Notification System API",
    description="Backend API for construction bidding information system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
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
# /external-bids 프리픽스. /bids 아래가 아닌 이유는 external_bids.py 주석 참조.
app.include_router(external_bids.router)
app.include_router(estimate_rate.router)
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
