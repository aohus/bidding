from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    user_id: UUID
    username: str
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


class UserPreferenceCreate(BaseModel):
    search_conditions: Dict[str, Any]


class UserPreferenceResponse(BaseModel):
    preference_id: UUID
    user_id: UUID
    search_conditions: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SavedSearchCreate(BaseModel):
    search_name: str = Field(..., min_length=1, max_length=100)
    filters: Dict[str, Any]


class SavedSearchResponse(BaseModel):
    search_id: UUID
    user_id: UUID
    search_name: str
    filters: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class BookmarkCreate(BaseModel):
    bid_notice_no: str
    bid_notice_name: str
    bid_notice_ord: Optional[str] = "000"
    status: str = "interested"  # interested | bid_completed
    bid_price: Optional[int] = None
    notes: Optional[str] = None


class BookmarkUpdate(BaseModel):
    status: Optional[str] = None
    bid_price: Optional[int] = None
    notes: Optional[str] = None


class BookmarkResponse(BaseModel):
    bookmark_id: UUID
    user_id: UUID
    bid_notice_no: str
    bid_notice_name: str
    bid_notice_ord: Optional[str] = None
    status: str
    bid_price: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # 공고 일정 enrichment
    bid_close_dt: Optional[str] = None
    openg_dt: Optional[str] = None
    openg_completed: bool = False
    # 개찰결과 enrichment (투찰완료 탭용)
    actual_bid_price: Optional[str] = None
    bid_rate: Optional[str] = None
    rank: Optional[str] = None
    total_bidders: Optional[int] = None
    # 낙찰자(1등) 정보
    winning_bid_price: Optional[str] = None
    winning_bid_rate: Optional[str] = None

    class Config:
        from_attributes = True


class BusinessProfileUpdate(BaseModel):
    business_number: Optional[str] = Field(None, max_length=20)
    company_name: Optional[str] = Field(None, max_length=200)
    representative_name: Optional[str] = Field(None, max_length=100)


class BusinessProfileResponse(BaseModel):
    business_number: Optional[str] = None
    company_name: Optional[str] = None
    representative_name: Optional[str] = None

    class Config:
        from_attributes = True