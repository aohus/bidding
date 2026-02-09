from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class NotificationSettings(BaseModel):
    """Schema for notification settings"""
    email_notifications_enabled: bool = True
    notification_frequency: str = 'daily'  # realtime, daily, weekly


class NotificationSettingsUpdate(BaseModel):
    """Schema for updating notification settings"""
    email_notifications_enabled: Optional[bool] = None
    notification_frequency: Optional[str] = None


class NotificationSettingsResponse(BaseModel):
    """Schema for notification settings response"""
    email_notifications_enabled: bool
    notification_frequency: str
    last_notification_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TestEmailRequest(BaseModel):
    """Schema for test email request"""
    email: EmailStr
    username: str