import logging

from app.api.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.bid import UserLocationCreate, UserLocationResponse
from app.services.bid_data_service import bid_data_service
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/locations", tags=["User Locations"])


@router.get("", response_model=UserLocationResponse)
async def get_location(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 소재지 조회"""
    location = await bid_data_service.get_user_location(db, current_user.user_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="소재지가 등록되지 않았습니다",
        )
    return UserLocationResponse(
        location_id=str(location.location_id),
        user_id=str(location.user_id),
        location_name=location.location_name,
    )


@router.post("", response_model=UserLocationResponse)
async def set_location(
    data: UserLocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 소재지 등록/수정"""
    location = await bid_data_service.set_user_location(
        db, current_user.user_id, data.location_name
    )
    return UserLocationResponse(
        location_id=str(location.location_id),
        user_id=str(location.user_id),
        location_name=location.location_name,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 소재지 삭제"""
    deleted = await bid_data_service.delete_user_location(db, current_user.user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="소재지가 등록되지 않았습니다",
        )
    return None
