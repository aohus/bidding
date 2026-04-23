from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_admin_user, get_current_user
from app.db.database import get_db
from app.models.user import User, UserBookmark
from app.schemas.bid import (
    BidApiResponse,
    BidAValueItem,
    BidItem,
    BidResultItem,
    BidResultResponse,
    BidSearchParams,
    DataSyncResponse,
    PrtcptPsblRgnItem,
)
from app.schemas.user import (
    BookmarkCreate,
    BookmarkOpengStatus,
    BookmarkResponse,
    BookmarkSortDir,
    BookmarkSortField,
    BookmarkUpdate,
    PaginatedBookmarkResponse,
)
from app.services.bid_data_service import bid_data_service
from app.services.narajangter import narajangter_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bids", tags=["Bid Notices"])

RESULT_PREOPEN_WINDOW_MINUTES = 30
RESULT_RETRY_COOLDOWN_MINUTES = 10
RESULT_ERROR_COOLDOWN_MINUTES = 3
RESULT_API_PAGE_SIZE = 100
RESULT_API_MAX_PAGES = 20
KST = ZoneInfo("Asia/Seoul")


def _now_kst() -> datetime:
    return datetime.now(KST)


def _parse_bid_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None

    clean = dt_str.replace("-", "").replace(":", "").replace(" ", "")[:12]
    if len(clean) < 12:
        return None

    try:
        return datetime.strptime(clean, "%Y%m%d%H%M").replace(tzinfo=KST)
    except (ValueError, TypeError):
        return None


async def _get_bid_open_datetime(
    db: AsyncSession,
    bid_ntce_no: str,
    bid_ntce_ord: str = "000",
) -> datetime | None:
    from app.models.bid import BidNotice

    result = await db.execute(
        select(BidNotice.openg_dt)
        .where(
            BidNotice.bid_ntce_no == bid_ntce_no,
            BidNotice.bid_ntce_ord == bid_ntce_ord,
        )
    )
    openg_dt_str = result.scalar_one_or_none()
    return _parse_bid_datetime(openg_dt_str)


def _can_attempt_bid_result_api(openg_dt: datetime | None, now: datetime) -> bool:
    if openg_dt is None:
        return True
    return now >= (openg_dt - timedelta(minutes=RESULT_PREOPEN_WINDOW_MINUTES))


async def _safe_upsert_bookmark_dashboard_item(
    db: AsyncSession,
    bookmark_id: Any,
) -> None:
    from app.services.bookmark_service import upsert_bookmark_dashboard_item

    try:
        async with db.begin_nested():
            await upsert_bookmark_dashboard_item(db, bookmark_id)
    except Exception:
        logger.warning(
            "bookmark_dashboard_upsert_failed",
            extra={"bookmark_id": str(bookmark_id)},
            exc_info=True,
        )


async def _safe_refresh_dashboard_for_notice(
    db: AsyncSession,
    bid_notice_no: str,
    bid_notice_ord: str,
) -> None:
    from app.services.bookmark_service import refresh_dashboard_for_notice

    try:
        async with db.begin_nested():
            await refresh_dashboard_for_notice(db, bid_notice_no, bid_notice_ord)
    except Exception:
        logger.warning(
            "bookmark_dashboard_refresh_for_notice_failed",
            extra={"bid_notice_no": bid_notice_no, "bid_notice_ord": bid_notice_ord},
            exc_info=True,
        )


@router.post("/search", response_model=BidApiResponse)
async def search_bids(
    search_params: BidSearchParams,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """입찰공고 검색 - DB 우선, API 폴백 (공고게시일시 div=1 기준만 동기화)

    API 호출 최소화 전략:
    - 날짜별 동기화 상태를 추적 (div=1 공고게시일시 기준)
    - synced → DB만 사용 (API 0회)
    - not synced → API 호출 → 저장 → synced 마킹
    - 개찰일시(div=2) 검색은 항상 DB에서 조회 (동기화된 데이터 활용)
    """
    logger.info(
        f"search_bids called by user: {current_user.username} with params: {search_params}"
    )
    try:
        inqry_div = search_params.inqryDiv
        start_date = search_params.inqryBgnDt[:8]
        end_date = search_params.inqryEndDt[:8]

        # 개찰일시(div=2) 검색은 항상 DB에서 조회
        if inqry_div == "2":
            return await bid_data_service.search_from_db(
                db, search_params, current_user.user_id
            )

        # div=1: 해당 날짜범위가 동기화 완료인지 확인
        is_synced = False
        try:
            is_synced = await bid_data_service.has_synced_data(
                db, start_date, end_date
            )
        except Exception as e:
            logger.warning(f"has_synced_data failed (migration not applied?): {e}")

        if is_synced:
            return await bid_data_service.search_from_db(
                db, search_params, current_user.user_id
            )

        # 동기화 안됨 → 공사+용역 API 호출
        api_params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt=search_params.inqryBgnDt,
            inqryEndDt=search_params.inqryEndDt,
            prtcptLmtRgnNm=search_params.prtcptLmtRgnNm,
            indstrytyNm=search_params.indstrytyNm,
            indstrytyCd=search_params.indstrytyCd,
            presmptPrceBgn=search_params.presmptPrceBgn,
            presmptPrceEnd=search_params.presmptPrceEnd,
            bidClseExcpYn=search_params.bidClseExcpYn,
            numOfRows=search_params.numOfRows,
            pageNo=search_params.pageNo,
        )
        cnstwk_result = await narajangter_service.search_bids(
            "contract", api_params
        )
        servc_result = await narajangter_service.search_bids(
            "service", api_params
        )

        # 결과 병합 (중복 제거)
        seen: set[str] = set()
        merged_items = []
        for item in list(cnstwk_result.items) + list(servc_result.items):
            key = f"{item.bidNtceNo}-{item.bidNtceOrd}"
            if key not in seen:
                seen.add(key)
                merged_items.append(item)

        result = BidApiResponse(
            items=merged_items,
            totalCount=len(merged_items),
            numOfRows=api_params.numOfRows,
            pageNo=api_params.pageNo,
        )

        # 백그라운드에서 날짜별 전체 동기화 (scheduler 활용)
        asyncio.create_task(
            _sync_date_range(start_date, end_date, result)
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search bids: {str(e)}",
        )


async def _sync_date_range(
    start_date: str,
    end_date: str,
    initial_result: BidApiResponse | None = None,
):
    """날짜 범위를 일별 윈도우로 동기화 (백그라운드).

    scheduler의 sync_window를 활용하여 공사+용역+지역+면허제한 모두 동기화.
    """
    from app.services.bid_sync_scheduler import bid_sync_scheduler

    try:
        if initial_result and initial_result.items:
            async with (await _get_session()) as db:
                await bid_data_service.save_bid_notices(db, initial_result.items)

        start_dt = datetime.strptime(start_date[:8], "%Y%m%d")
        end_dt = datetime.strptime(end_date[:8], "%Y%m%d")
        current = start_dt

        while current <= end_dt:
            d = current.strftime("%Y%m%d")
            await bid_sync_scheduler.sync_window(d + "0000", d + "2359")
            current += timedelta(days=1)
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Background sync failed: {e}")


async def _get_session():
    """비동기 세션 팩토리 (백그라운드 작업용)"""
    from app.db.database import AsyncSessionLocal

    return AsyncSessionLocal()


def _has_bssamt(item: BidAValueItem) -> bool:
    """기초금액이 존재하는지 확인"""
    return item.bssamt is not None and item.bssamt.strip() != "" and item.bssamt != "0"


BSSAMT_RETRY_WINDOW_DAYS = 3
BSSAMT_RETRY_COOLDOWN_HOURS = 1


async def _should_retry_bssamt(
    db: AsyncSession,
    bid_ntce_no: str,
    fetched_at: datetime | None,
) -> bool:
    """bssamt 미공개 시 API 재시도 여부를 판단합니다.

    조건: (개찰일 3일 이내 또는 개찰일 경과) + 마지막 조회 후 1시간 경과
    개찰일이 3일 넘게 남은 경우에만 재시도하지 않음 (아직 공개 전)
    """
    from app.models.bid import BidNotice
    from datetime import timezone

    # 1. 쿨다운 확인 (fetched_at이 1시간 이내면 skip)
    if fetched_at:
        now = datetime.now(timezone.utc)
        fetched_utc = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=timezone.utc)
        if (now - fetched_utc) < timedelta(hours=BSSAMT_RETRY_COOLDOWN_HOURS):
            return False

    # 2. 개찰일 3일 이내인지 확인
    result = await db.execute(
        select(BidNotice.openg_dt).where(
            BidNotice.bid_ntce_no == bid_ntce_no,
        )
    )
    openg_dt_str = result.scalar_one_or_none()
    if not openg_dt_str:
        return True  # 개찰일 정보 없으면 시도

    try:
        # YYYYMMDDHHMM 또는 "YYYY-MM-DD HH:MM:SS" 포맷 처리
        clean = openg_dt_str.replace("-", "").replace(":", "").replace(" ", "")[:12]
        openg_dt = datetime.strptime(clean, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_until_openg = (openg_dt - now).total_seconds() / 86400
        return days_until_openg <= BSSAMT_RETRY_WINDOW_DAYS
    except (ValueError, TypeError):
        return True  # 파싱 실패 시 시도


async def _fetch_and_cache_a_value(
    db: AsyncSession, bidNtceNo: str, bid_type: str
) -> BidAValueItem | None:
    """나라장터 API에서 A값을 조회하고 DB에 캐싱"""
    result = await narajangter_service.get_bid_a_value(
        bidNtceNo, bid_type=bid_type
    )
    if result:
        await bid_data_service.save_basis_amount(
            db, bidNtceNo, bid_type, result.model_dump()
        )
    return result


async def _refresh_bid_notice(
    db: AsyncSession, bidNtceNo: str, bid_type: str
) -> BidItem | None:
    """공고검색 API에서 공고 데이터를 재조회하여 bid_notices를 갱신합니다.

    기초금액 미공개 시 asignBdgtAmt(배정예산금액)을 확보하기 위해 사용.
    요청된 bid_type으로 먼저 시도, 실패 시 다른 타입으로 재시도.
    """
    for try_type in [bid_type, "servc" if bid_type == "cnstwk" else "cnstwk"]:
        result = await narajangter_service.get_bid_notice_by_no(
            bidNtceNo, bid_type=try_type
        )
        if result:
            await bid_data_service.save_bid_notices(db, [result])
            logger.info(
                f"Refreshed bid notice {bidNtceNo} via 공고 API ({try_type}), "
                f"asignBdgtAmt={result.asignBdgtAmt}"
            )
            return result
    return None


@router.get("/a-value/{bidNtceNo}/", response_model=BidAValueItem)
async def get_bid_a_value(
    bidNtceNo: str,
    bid_type: str = "cnstwk",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A값 조회 - DB 캐시 우선, bssamt 없으면 재조회, 양쪽 bid_type 시도"""
    logger.info(
        f"get_bid_a_value called by user: {current_user.username} "
        f"for bidNtceNo: {bidNtceNo} with type: {bid_type}"
    )
    try:
        # 1. DB 캐시 조회
        cached = await bid_data_service.get_basis_amount_from_db(
            db, bidNtceNo, bid_type
        )
        if cached and _has_bssamt(cached):
            return cached

        # 2. 캐시에 bssamt 없음 → A값 API 조회 (요청된 bid_type)
        result = await _fetch_and_cache_a_value(db, bidNtceNo, bid_type)
        if result and _has_bssamt(result):
            return result

        # 3. 다른 bid_type으로도 A값 시도
        alt_type = "servc" if bid_type == "cnstwk" else "cnstwk"
        alt_cached = await bid_data_service.get_basis_amount_from_db(
            db, bidNtceNo, alt_type
        )
        if alt_cached and _has_bssamt(alt_cached):
            return alt_cached

        alt_result = await _fetch_and_cache_a_value(db, bidNtceNo, alt_type)
        if alt_result and _has_bssamt(alt_result):
            return alt_result

        # 4. bssamt 없음 → 공고 API로 bid_notices 갱신 (asignBdgtAmt 확보)
        best = result or alt_result or cached or alt_cached
        if best and not _has_bssamt(best):
            cached_row = await bid_data_service.get_basis_amount_row(
                db, bidNtceNo, bid_type
            )
            should_retry = await _should_retry_bssamt(
                db, bidNtceNo, cached_row.fetched_at if cached_row else None
            )
            if should_retry:
                await _refresh_bid_notice(db, bidNtceNo, bid_type)
                # 쿨다운 타이머 리셋
                if cached_row:
                    await bid_data_service.touch_basis_amount_fetched_at(
                        db, bidNtceNo, bid_type
                    )

        # 5. 어느 쪽이든 데이터가 있으면 반환
        if best:
            return best

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A-value information not found",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching A-value: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch A-value information: {str(e)}",
        )


@router.get("/{bidNtceNo}/detail", response_model=BidItem)
async def get_bid_detail(
    bidNtceNo: str,
    bidNtceOrd: str = "000",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """DB에서 공고 상세 정보를 조회합니다."""
    from app.models.bid import BidNotice

    result = await db.execute(
        select(BidNotice).where(
            BidNotice.bid_ntce_no == bidNtceNo,
            BidNotice.bid_ntce_ord == bidNtceOrd,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bid notice not found",
        )
    return BidItem(**row.data)


@router.get(
    "/{bidNtceNo}/regions",
    response_model=List[PrtcptPsblRgnItem],
)
async def get_bid_regions(
    bidNtceNo: str,
    bidNtceOrd: str = "000",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공고의 참가가능지역 조회"""
    from app.models.bid import BidPrtcptPsblRgn

    # DB에서 먼저 조회
    result = await db.execute(
        select(BidPrtcptPsblRgn).where(
            BidPrtcptPsblRgn.bid_ntce_no == bidNtceNo,
            BidPrtcptPsblRgn.bid_ntce_ord == bidNtceOrd,
        )
    )
    db_regions = result.scalars().all()

    if db_regions:
        return [
            PrtcptPsblRgnItem(
                bidNtceNo=r.bid_ntce_no,
                bidNtceOrd=r.bid_ntce_ord,
                lmtSno=r.lmt_sno,
                prtcptPsblRgnNm=r.prtcpt_psbl_rgn_nm,
                rgstDt=r.rgst_dt,
                bsnsDivNm=r.bsns_div_nm,
            )
            for r in db_regions
        ]

    # DB에 없으면 API 조회 후 저장
    api_regions = await narajangter_service.get_prtcpt_psbl_rgn_by_bid(
        bidNtceNo, bidNtceOrd
    )
    if api_regions:
        await bid_data_service.save_prtcpt_psbl_rgns(db, api_regions)

    return api_regions


@router.post("/sync", response_model=DataSyncResponse)
async def trigger_sync(
    days: int = 30,
    current_user: User = Depends(get_admin_user),
):
    """데이터 동기화 트리거 (백그라운드 실행)"""
    from app.services.bid_sync_scheduler import bid_sync_scheduler

    asyncio.create_task(bid_sync_scheduler.sync_recent_data(days=days))

    return DataSyncResponse(
        synced=False,
        total_notices=0,
        total_regions=0,
        message=f"최근 {days}일 동기화가 백그라운드에서 시작되었습니다.",
    )


# --- Bookmark endpoints ---


@router.post(
    "/bookmarks",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark(
    bookmark_data: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new bookmark for a bid notice."""
    result = await db.execute(
        select(UserBookmark).where(
            UserBookmark.user_id == current_user.user_id,
            UserBookmark.bid_notice_no == bookmark_data.bid_notice_no,
        )
    )
    existing_bookmark = result.scalar_one_or_none()

    if existing_bookmark:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookmark already exists",
        )

    new_bookmark = UserBookmark(
        user_id=current_user.user_id,
        bid_notice_no=bookmark_data.bid_notice_no,
        bid_notice_name=bookmark_data.bid_notice_name,
        bid_notice_ord=bookmark_data.bid_notice_ord,
        status=bookmark_data.status,
        bid_price=bookmark_data.bid_price,
        notes=bookmark_data.notes,
    )

    db.add(new_bookmark)
    await db.flush()
    await db.refresh(new_bookmark)
    await _safe_upsert_bookmark_dashboard_item(db, new_bookmark.bookmark_id)
    await db.commit()
    await db.refresh(new_bookmark)

    return new_bookmark


@router.get("/bookmarks", response_model=PaginatedBookmarkResponse)
async def get_bookmarks(
    bookmark_status: str = "bid_completed",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_field: BookmarkSortField = "openg_dt",
    sort_dir: BookmarkSortDir = "desc",
    openg_status: BookmarkOpengStatus = "all",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """북마크 목록 페이지네이션 조회 (서버 사이드 정렬/필터)"""
    from app.services.bookmark_service import get_paginated_bookmarks

    return await get_paginated_bookmarks(
        db=db,
        user=current_user,
        status=bookmark_status,
        page=page,
        page_size=page_size,
        sort_field=sort_field,
        sort_dir=sort_dir,
        openg_status=openg_status,
    )


@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkResponse)
async def update_bookmark(
    bookmark_id: str,
    update_data: BookmarkUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a bookmark (status, bid_price, notes)."""
    result = await db.execute(
        select(UserBookmark).where(
            UserBookmark.bookmark_id == bookmark_id,
            UserBookmark.user_id == current_user.user_id,
        )
    )
    bookmark = result.scalar_one_or_none()

    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found",
        )

    if update_data.status is not None:
        bookmark.status = update_data.status
    if update_data.bid_price is not None:
        bookmark.bid_price = update_data.bid_price
    if update_data.notes is not None:
        bookmark.notes = update_data.notes

    await db.flush()
    await db.refresh(bookmark)
    await _safe_upsert_bookmark_dashboard_item(db, bookmark.bookmark_id)
    await db.commit()
    await db.refresh(bookmark)
    return bookmark


@router.delete(
    "/bookmarks/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_bookmark(
    bookmark_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a bookmark."""
    result = await db.execute(
        select(UserBookmark).where(
            UserBookmark.bookmark_id == bookmark_id,
            UserBookmark.user_id == current_user.user_id,
        )
    )
    bookmark = result.scalar_one_or_none()

    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found",
        )

    await db.delete(bookmark)
    await db.commit()

    return None


# --- Bid Opening Results ---


@router.get("/{bidNtceNo}/results", response_model=BidResultResponse)
async def get_bid_results(
    bidNtceNo: str,
    bidNtceOrd: str = "000",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """개찰결과 조회 (캐시 → API 폴백)

    data=NULL  → 에러 쿨다운 (RESULT_ERROR_COOLDOWN_MINUTES)
    data=[]    → 빈 결과 쿨다운 (RESULT_RETRY_COOLDOWN_MINUTES)
    data=[...] → 유효한 캐시, API 호출 없이 반환
    """
    from app.models.bid import BidOpeningResult
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.sql import func

    # 1. 캐시 확인
    result = await db.execute(
        select(BidOpeningResult).where(
            BidOpeningResult.bid_ntce_no == bidNtceNo,
            BidOpeningResult.bid_ntce_ord == bidNtceOrd,
        )
    )
    cached = result.scalar_one_or_none()

    now = _now_kst()
    openg_dt = await _get_bid_open_datetime(db, bidNtceNo, bidNtceOrd)

    def _age_seconds(fetched_at: datetime | None) -> float:
        if fetched_at is None:
            return 0.0
        utc = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - utc).total_seconds()

    items_data: list[dict[str, Any]] | None = None
    if cached:
        if cached.data:
            # 유효한 결과 → 캐시 반환
            items_data = cached.data
        elif cached.data is None:
            # 에러 상태 → 3분 쿨다운
            if _age_seconds(cached.fetched_at) < RESULT_ERROR_COOLDOWN_MINUTES * 60:
                items_data = []
        else:
            # 빈 결과([]) → 10분 쿨다운
            if (
                cached.fetched_at is None
                or _age_seconds(cached.fetched_at) < RESULT_RETRY_COOLDOWN_MINUTES * 60
            ):
                items_data = []

    if items_data is None and not _can_attempt_bid_result_api(openg_dt, now):
        items_data = (cached.data or []) if cached else []

    async def _upsert_result(data: list[dict[str, Any]] | None) -> None:
        stmt = (
            pg_insert(BidOpeningResult)
            .values(bid_ntce_no=bidNtceNo, bid_ntce_ord=bidNtceOrd, data=data)
            .on_conflict_do_update(
                index_elements=["bid_ntce_no", "bid_ntce_ord"],
                set_={"data": data, "fetched_at": func.now()},
            )
        )
        await db.execute(stmt)
        await _safe_refresh_dashboard_for_notice(db, bidNtceNo, bidNtceOrd)
        await db.commit()

    if items_data is None:
        # 2. API 호출
        try:
            all_items: list[BidResultItem] = []
            for page in range(1, RESULT_API_MAX_PAGES + 1):
                page_items = await narajangter_service.get_bid_opening_results(
                    bidNtceNo, pageNo=page, numOfRows=RESULT_API_PAGE_SIZE
                )
                if not page_items:
                    break
                all_items.extend(page_items)
                if len(page_items) < RESULT_API_PAGE_SIZE:
                    break
            else:
                logger.warning(
                    "bid_result_pagination_limit_reached",
                    extra={"bid_ntce_no": bidNtceNo},
                )

            items_data = [item.model_dump() for item in all_items]

            # 3. 캐시 저장 (성공: data=[] 또는 data=[...])
            await _upsert_result(items_data)
        except Exception as e:
            logger.error(
                "bid_result_fetch_failed",
                extra={"bid_ntce_no": bidNtceNo, "error": str(e)},
                exc_info=True,
            )
            # 실패: data=NULL 저장 → 3분 에러 쿨다운 (10분 빈 결과 쿨다운과 분리)
            items_data = []
            try:
                await _upsert_result(None)
            except Exception:
                await db.rollback()

    # 4. 결과 빌드
    results = [BidResultItem(**item) for item in items_data]

    # 5. 사업자번호 매칭
    user_rank = None
    if current_user.business_number:
        normalized_biz = current_user.business_number.replace("-", "")
        for item in results:
            if item.prcbdrBizno and item.prcbdrBizno.replace("-", "") == normalized_biz:
                user_rank = item
                break

    return BidResultResponse(
        bid_ntce_no=bidNtceNo,
        results=results,
        user_rank=user_rank,
        total_bidders=len(results),
    )
