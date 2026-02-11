from app.api.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import BusinessProfileResponse, BusinessProfileUpdate
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/profile", tags=["User Profile"])


@router.get("/business", response_model=BusinessProfileResponse)
async def get_business_profile(
    current_user: User = Depends(get_current_user),
):
    """사업자정보 조회"""
    return BusinessProfileResponse(
        business_number=current_user.business_number,
        company_name=current_user.company_name,
        representative_name=current_user.representative_name,
    )


@router.put("/business", response_model=BusinessProfileResponse)
async def update_business_profile(
    data: BusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사업자정보 수정"""
    if data.business_number is not None:
        current_user.business_number = data.business_number
    if data.company_name is not None:
        current_user.company_name = data.company_name
    if data.representative_name is not None:
        current_user.representative_name = data.representative_name

    await db.commit()
    await db.refresh(current_user)

    return BusinessProfileResponse(
        business_number=current_user.business_number,
        company_name=current_user.company_name,
        representative_name=current_user.representative_name,
    )
