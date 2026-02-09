from datetime import datetime

from app.api.auth import get_current_user
from app.db.database import get_db
from app.models.user import User, UserPreference
from app.schemas.notification import (
    NotificationSettings,
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    TestEmailRequest,
)
from app.services.email_service import email_service
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's notification settings
    """
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.user_id)
    )
    preference = result.scalar_one_or_none()
    
    if not preference:
        # Return default settings if no preference exists
        return NotificationSettingsResponse(
            email_notifications_enabled=True,
            notification_frequency='daily',
            last_notification_at=None
        )
    
    return NotificationSettingsResponse(
        email_notifications_enabled=preference.email_notifications_enabled,
        notification_frequency=preference.notification_frequency,
        last_notification_at=preference.last_notification_at
    )


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    settings: NotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update notification settings for current user
    """
    # Get existing preference
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.user_id)
    )
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=404,
            detail="User preferences not found. Please save search conditions first."
        )
    
    # Update notification settings
    update_data = {}
    if settings.email_notifications_enabled is not None:
        update_data['email_notifications_enabled'] = settings.email_notifications_enabled
    if settings.notification_frequency is not None:
        # Validate frequency
        if settings.notification_frequency not in ['realtime', 'daily', 'weekly']:
            raise HTTPException(
                status_code=400,
                detail="Invalid notification frequency. Must be 'realtime', 'daily', or 'weekly'."
            )
        update_data['notification_frequency'] = settings.notification_frequency
    
    if update_data:
        update_data['updated_at'] = datetime.now()
        await db.execute(
            update(UserPreference)
            .where(UserPreference.user_id == current_user.user_id)
            .values(**update_data)
        )
        await db.commit()
        
        # Refresh preference
        await db.refresh(preference)
    
    return NotificationSettingsResponse(
        email_notifications_enabled=preference.email_notifications_enabled,
        notification_frequency=preference.notification_frequency,
        last_notification_at=preference.last_notification_at
    )


@router.post("/test-email")
async def send_test_email(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Send a test email to current user
    """
    # Send test email in background
    background_tasks.add_task(
        email_service.send_welcome_email,
        to_email=current_user.email,
        username=current_user.username
    )
    
    return {
        "message": f"Test email will be sent to {current_user.email}",
        "status": "queued"
    }


@router.post("/send-bid-notification")
async def send_test_bid_notification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Send a test bid notification email with sample data
    """
    # Sample bid notices for testing
    sample_bids = [
        {
            "bidNtceNo": "20250117001",
            "bidNtceNm": "서울시 도로 건설 공사",
            "ntceInsttNm": "서울특별시",
            "presmptPrce": 1000000000,
            "bidClseDt": "2025-01-25 10:00",
            "opengDt": "2025-01-25 14:00"
        },
        {
            "bidNtceNo": "20250117002",
            "bidNtceNm": "교량 보수 공사",
            "ntceInsttNm": "경기도청",
            "presmptPrce": 500000000,
            "bidClseDt": "2025-01-26 10:00",
            "opengDt": "2025-01-26 14:00"
        }
    ]
    
    # Send test notification in background
    background_tasks.add_task(
        email_service.send_bid_notification,
        to_email=current_user.email,
        username=current_user.username,
        bid_notices=sample_bids
    )
    
    return {
        "message": f"Test bid notification will be sent to {current_user.email}",
        "status": "queued"
    }