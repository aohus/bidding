import uuid

from app.db.database import Base
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    preference_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    search_conditions = Column(JSONB, nullable=False)
    
    # Email notification settings
    email_notifications_enabled = Column(Boolean, default=True, nullable=False)
    notification_frequency = Column(String(20), default='daily', nullable=False)  # realtime, daily, weekly
    last_notification_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    
    search_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    search_name = Column(String(100), nullable=False)
    filters = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserBookmark(Base):
    __tablename__ = "user_bookmarks"
    
    bookmark_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    bid_notice_no = Column(String(50), nullable=False, index=True)
    bid_notice_name = Column(String(500), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())