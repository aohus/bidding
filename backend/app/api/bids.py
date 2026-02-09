import logging
from typing import List

from app.api.auth import get_current_user
from app.db.database import get_db
from app.models.user import User, UserBookmark
from app.schemas.bid import BidApiResponse, BidSearchParams, BidAValueItem
from app.schemas.user import BookmarkCreate, BookmarkResponse
from app.services.narajangter import narajangter_service
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bids", tags=["Bid Notices"])


@router.post("/search", response_model=BidApiResponse)
async def search_bids(
    search_params: BidSearchParams,
    current_user: User = Depends(get_current_user)
):
    """Search for bid notices using 나라장터 API."""
    logger.info(f"search_bids called by user: {current_user.username} with params: {search_params}")
    try:
        result = await narajangter_service.search_bids(search_params)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search bids: {str(e)}"
        )


@router.get("/a-value/{bidNtceNo}/", response_model=BidAValueItem)
async def get_bid_a_value(
    bidNtceNo: str,
    bid_type: str = "cnstwk",
    current_user: User = Depends(get_current_user)
):
    """Get A-value information for a specific bid notice."""
    logger.info(f"get_bid_a_value called by user: {current_user.username} for bidNtceNo: {bidNtceNo} with type: {bid_type}")
    try:
        result = await narajangter_service.get_bid_a_value(bidNtceNo, bid_type=bid_type)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A-value information not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching A-value: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch A-value information: {str(e)}"
        )


@router.post("/bookmarks", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    bookmark_data: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new bookmark for a bid notice."""
    # Check if bookmark already exists
    result = await db.execute(
        select(UserBookmark).where(
            UserBookmark.user_id == current_user.user_id,
            UserBookmark.bid_notice_no == bookmark_data.bid_notice_no
        )
    )
    existing_bookmark = result.scalar_one_or_none()
    
    if existing_bookmark:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookmark already exists"
        )
    
    new_bookmark = UserBookmark(
        user_id=current_user.user_id,
        bid_notice_no=bookmark_data.bid_notice_no,
        bid_notice_name=bookmark_data.bid_notice_name,
        notes=bookmark_data.notes
    )
    
    db.add(new_bookmark)
    await db.commit()
    await db.refresh(new_bookmark)
    
    return new_bookmark


@router.get("/bookmarks", response_model=List[BookmarkResponse])
async def get_bookmarks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all bookmarks for current user."""
    result = await db.execute(
        select(UserBookmark).where(UserBookmark.user_id == current_user.user_id)
    )
    bookmarks = result.scalars().all()
    
    return bookmarks


@router.delete("/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a bookmark."""
    result = await db.execute(
        select(UserBookmark).where(
            UserBookmark.bookmark_id == bookmark_id,
            UserBookmark.user_id == current_user.user_id
        )
    )
    bookmark = result.scalar_one_or_none()
    
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found"
        )
    
    await db.delete(bookmark)
    await db.commit()
    
    return None