import logging
from uuid import UUID

from app.api.auth import get_current_user
from app.db.database import AsyncSessionLocal, get_db
from app.models.user import User
from app.schemas.user import BusinessProfileResponse, BusinessProfileUpdate
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/profile", tags=["User Profile"])
logger = logging.getLogger(__name__)


async def _refresh_dashboard_for_user_background(
    user_id: UUID, business_number: str | None
) -> None:
    from app.services.bookmark_service import refresh_dashboard_for_user

    async with AsyncSessionLocal() as db:
        try:
            await refresh_dashboard_for_user(db, user_id, business_number)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.warning(
                "bookmark_dashboard_refresh_for_user_failed",
                extra={"user_id": str(user_id)},
                exc_info=True,
            )


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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사업자정보 수정"""
    business_number_changed = (
        data.business_number is not None
        and data.business_number != current_user.business_number
    )

    if data.business_number is not None:
        current_user.business_number = data.business_number
    if data.company_name is not None:
        current_user.company_name = data.company_name
    if data.representative_name is not None:
        current_user.representative_name = data.representative_name

    await db.commit()
    await db.refresh(current_user)
    if business_number_changed:
        background_tasks.add_task(
            _refresh_dashboard_for_user_background,
            current_user.user_id,
            current_user.business_number,
        )

    return BusinessProfileResponse(
        business_number=current_user.business_number,
        company_name=current_user.company_name,
        representative_name=current_user.representative_name,
    )
