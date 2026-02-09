from typing import List

from app.api.auth import get_current_user
from app.db.database import get_db
from app.models.user import SavedSearch, User, UserPreference
from app.schemas.user import (
    SavedSearchCreate,
    SavedSearchResponse,
    UserPreferenceCreate,
    UserPreferenceResponse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/preferences", tags=["User Preferences"])


@router.post("/", response_model=UserPreferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_preference(
    preference_data: UserPreferenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create or update user's default search preferences."""
    # Check if preference already exists
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.user_id)
    )
    existing_preference = result.scalar_one_or_none()
    
    if existing_preference:
        # Update existing preference
        existing_preference.search_conditions = preference_data.search_conditions
        await db.commit()
        await db.refresh(existing_preference)
        return existing_preference
    else:
        # Create new preference
        new_preference = UserPreference(
            user_id=current_user.user_id,
            search_conditions=preference_data.search_conditions
        )
        db.add(new_preference)
        await db.commit()
        await db.refresh(new_preference)
        return new_preference


@router.get("/", response_model=UserPreferenceResponse)
async def get_preference(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's default search preferences."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.user_id)
    )
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preferences found"
        )
    
    return preference


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user's default search preferences."""
    await db.execute(
        delete(UserPreference).where(UserPreference.user_id == current_user.user_id)
    )
    await db.commit()
    return None


@router.post("/searches", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    search_data: SavedSearchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new saved search."""
    new_search = SavedSearch(
        user_id=current_user.user_id,
        search_name=search_data.search_name,
        filters=search_data.filters
    )
    
    db.add(new_search)
    await db.commit()
    await db.refresh(new_search)
    
    return new_search


@router.get("/searches", response_model=List[SavedSearchResponse])
async def get_saved_searches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all saved searches for current user."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.user_id == current_user.user_id)
    )
    searches = result.scalars().all()
    
    return searches


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a saved search."""
    result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.search_id == search_id,
            SavedSearch.user_id == current_user.user_id
        )
    )
    search = result.scalar_one_or_none()
    
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    await db.delete(search)
    await db.commit()
    
    return None