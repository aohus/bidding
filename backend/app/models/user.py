import uuid

from app.db.database import Base
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    business_number = Column(String(20), nullable=True, index=True)  # 사업자등록번호
    company_name = Column(String(200), nullable=True)  # 업체명
    representative_name = Column(String(100), nullable=True)  # 대표자명
    is_admin = Column(Boolean, default=False, nullable=False, server_default="false")
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
    __table_args__ = (
        Index("ix_user_bookmarks_user_status_created", "user_id", "status", "created_at"),
        Index("ix_user_bookmarks_notice_ord", "bid_notice_no", "bid_notice_ord"),
    )
    
    bookmark_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    bid_notice_no = Column(String(50), nullable=False, index=True)
    bid_notice_name = Column(String(500), nullable=False)
    bid_notice_ord = Column(String(10), nullable=True, default="000")
    status = Column(String(20), nullable=False, server_default="interested")  # interested | bid_completed
    bid_price = Column(BigInteger, nullable=True)  # 투찰가
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BookmarkDashboardItem(Base):
    __tablename__ = "bookmark_dashboard_items"
    __table_args__ = (
        Index(
            "ix_bookmark_dashboard_user_status_openg",
            "user_id",
            "status",
            "openg_dt",
        ),
        Index(
            "ix_bookmark_dashboard_user_status_close",
            "user_id",
            "status",
            "bid_close_dt",
        ),
        Index(
            "ix_bookmark_dashboard_user_status_created",
            "user_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_bookmark_dashboard_user_status_rank",
            "user_id",
            "status",
            "rank_value",
        ),
        Index(
            "ix_bookmark_dashboard_notice_ord",
            "bid_notice_no",
            "bid_notice_ord",
        ),
    )

    bookmark_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_bookmarks.bookmark_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False)
    bid_notice_no = Column(String(50), nullable=False)
    bid_notice_ord = Column(String(10), nullable=True, default="000")
    bid_notice_name = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False)
    bid_price = Column(BigInteger, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    bid_close_dt = Column(String(14), nullable=True)
    openg_dt = Column(String(14), nullable=True)
    openg_completed = Column(Boolean, nullable=False, server_default="false")
    actual_bid_price = Column(String(50), nullable=True)
    bid_rate = Column(String(50), nullable=True)
    rank_value = Column(Integer, nullable=True)
    total_bidders = Column(Integer, nullable=True)
    winning_bid_price = Column(String(50), nullable=True)
    winning_bid_rate = Column(String(50), nullable=True)
