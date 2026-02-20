from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.schemas.user import BookmarkCreate, BookmarkResponse, BookmarkUpdate
from app.services.bid_data_service import bid_data_service
from app.services.narajangter import narajangter_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bids", tags=["Bid Notices"])


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

    조건: 개찰일 3일 이내 + 마지막 조회 후 1시간 경과
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


def _has_rate_fields(item: BidAValueItem) -> bool:
    """예비가격범위율이 존재하는지 확인 (값이 "0"일 수 있으므로 None/빈문자열만 체크)"""
    return (
        item.rsrvtnPrceRngBgnRate is not None
        and item.rsrvtnPrceRngBgnRate != ""
        and item.rsrvtnPrceRngEndRate is not None
        and item.rsrvtnPrceRngEndRate != ""
    )


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


@router.get("/a-value/{bidNtceNo}/", response_model=BidAValueItem)
async def get_bid_a_value(
    bidNtceNo: str,
    bid_type: str = "cnstwk",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A값 조회 - DB 캐시 우선, rate 필드 없으면 재조회, 양쪽 bid_type 시도"""
    logger.info(
        f"get_bid_a_value called by user: {current_user.username} "
        f"for bidNtceNo: {bidNtceNo} with type: {bid_type}"
    )
    try:
        # 0. bssamt 미공개 캐시 쿨다운 체크
        cached_row = await bid_data_service.get_basis_amount_row(
            db, bidNtceNo, bid_type
        )
        if cached_row:
            cached_item = BidAValueItem(**cached_row.data)
            if not _has_bssamt(cached_item):
                should_retry = await _should_retry_bssamt(
                    db, bidNtceNo, cached_row.fetched_at
                )
                if not should_retry:
                    logger.info(
                        f"bssamt cooldown active for {bidNtceNo}, returning cached"
                    )
                    return cached_item

        # 1. DB 캐시 조회
        cached = await bid_data_service.get_basis_amount_from_db(
            db, bidNtceNo, bid_type
        )
        if cached and _has_rate_fields(cached) and _has_bssamt(cached):
            return cached

        # 2. 캐시에 rate/bssamt 없음 → API 재조회 (요청된 bid_type)
        result = await _fetch_and_cache_a_value(db, bidNtceNo, bid_type)
        if result and _has_rate_fields(result):
            return result

        # API 결과에 bssamt 없으면 fetched_at 갱신 (쿨다운 타이머 리셋)
        if cached_row and not (result and _has_bssamt(result)):
            await bid_data_service.touch_basis_amount_fetched_at(
                db, bidNtceNo, bid_type
            )

        # 3. 다른 bid_type으로도 시도
        alt_type = "servc" if bid_type == "cnstwk" else "cnstwk"
        alt_cached = await bid_data_service.get_basis_amount_from_db(
            db, bidNtceNo, alt_type
        )
        if alt_cached and _has_rate_fields(alt_cached):
            return alt_cached

        alt_result = await _fetch_and_cache_a_value(db, bidNtceNo, alt_type)
        if alt_result and _has_rate_fields(alt_result):
            return alt_result

        # 4. 어느 쪽이든 데이터가 있으면 rate 없이라도 반환
        best = result or alt_result or cached or alt_cached
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
    await db.commit()
    await db.refresh(new_bookmark)

    return new_bookmark


@router.get("/bookmarks", response_model=List[BookmarkResponse])
async def get_bookmarks(
    bookmark_status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get bookmarks for current user, optionally filtered by status."""
    from app.models.bid import BidNotice, BidOpeningResult

    query = select(UserBookmark).where(
        UserBookmark.user_id == current_user.user_id
    )
    if bookmark_status:
        query = query.where(UserBookmark.status == bookmark_status)
    query = query.order_by(UserBookmark.created_at.desc())

    result = await db.execute(query)
    bookmarks = result.scalars().all()

    all_bid_nos = [b.bid_notice_no for b in bookmarks]

    # 공고 일정 enrichment (bid_close_dt, openg_dt)
    notice_map: dict[str, dict] = {}
    if all_bid_nos:
        notice_res = await db.execute(
            select(
                BidNotice.bid_ntce_no,
                BidNotice.bid_close_dt,
                BidNotice.openg_dt,
            ).where(BidNotice.bid_ntce_no.in_(all_bid_nos))
        )
        for row in notice_res.all():
            notice_map[row[0]] = {
                "bid_close_dt": row[1],
                "openg_dt": row[2],
            }

    # 개찰결과 enrichment
    results_map: dict[str, dict] = {}
    if all_bid_nos:
        res = await db.execute(
            select(BidOpeningResult).where(
                BidOpeningResult.bid_ntce_no.in_(all_bid_nos)
            )
        )
        for row in res.scalars().all():
            results_map[row.bid_ntce_no] = {
                "data": row.data,
                "total": len(row.data) if row.data else 0,
            }

    normalized_biz = ""
    if current_user.business_number:
        normalized_biz = current_user.business_number.replace("-", "")

    enriched = []
    for b in bookmarks:
        resp = BookmarkResponse.model_validate(b)

        # 공고 일정
        if b.bid_notice_no in notice_map:
            nd = notice_map[b.bid_notice_no]
            resp.bid_close_dt = nd["bid_close_dt"]
            resp.openg_dt = nd["openg_dt"]

        # 개찰완료 여부
        resp.openg_completed = b.bid_notice_no in results_map

        if b.status == "bid_completed" and b.bid_notice_no in results_map:
            cached = results_map[b.bid_notice_no]
            resp.total_bidders = cached["total"]

            if cached["data"]:
                # 낙찰자(1등) 정보
                for item in cached["data"]:
                    if item.get("opengRank") == "1":
                        resp.winning_bid_price = item.get("bidprcAmt")
                        resp.winning_bid_rate = item.get("bidprcrt")
                        break

                # 내 투찰 정보 + 마이너스 등수 계산
                if normalized_biz:
                    # opengRank 없는 업체 = 미달
                    # 투찰률 내림차순으로 -1, -2, ... 부여
                    unranked = []
                    for r in cached["data"]:
                        rank_val = (r.get("opengRank") or "").strip()
                        if not rank_val:
                            try:
                                rate = float(r.get("bidprcrt") or "0")
                            except (ValueError, TypeError):
                                rate = 0.0
                            biz_r = (r.get("prcbdrBizno") or "").replace(
                                "-", ""
                            )
                            unranked.append((rate, biz_r))
                    # 투찰률 높은 순 (threshold에 가까운 순) = -1
                    unranked.sort(key=lambda x: x[0], reverse=True)

                    for item in cached["data"]:
                        biz = (item.get("prcbdrBizno") or "").replace("-", "")
                        if biz == normalized_biz:
                            resp.actual_bid_price = item.get("bidprcAmt")
                            resp.bid_rate = item.get("bidprcrt")

                            rank_val = (
                                item.get("opengRank") or ""
                            ).strip()
                            if rank_val:
                                resp.rank = rank_val
                            else:
                                # 미달 업체 중 순서 찾기
                                for idx, (_, ubiz) in enumerate(unranked):
                                    if ubiz == normalized_biz:
                                        resp.rank = str(-(idx + 1))
                                        break
                            break

        if resp.actual_bid_price is None and b.bid_price:
            resp.actual_bid_price = str(b.bid_price)

        enriched.append(resp)

    return enriched


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """개찰결과 조회 (캐시 → API 폴백)"""
    from app.models.bid import BidOpeningResult
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # 1. 캐시 확인
    result = await db.execute(
        select(BidOpeningResult).where(
            BidOpeningResult.bid_ntce_no == bidNtceNo
        )
    )
    cached = result.scalar_one_or_none()

    items_data = None
    if cached:
        # 1시간 이내 캐시 사용
        from sqlalchemy.sql import func
        age = datetime.now(cached.fetched_at.tzinfo) - cached.fetched_at
        if age.total_seconds() < 3600:
            items_data = cached.data

    if items_data is None:
        # 2. API 호출
        try:
            all_items: list[BidResultItem] = []
            page = 1
            while True:
                page_items = await narajangter_service.get_bid_opening_results(
                    bidNtceNo, pageNo=page, numOfRows=100
                )
                if not page_items:
                    break
                all_items.extend(page_items)
                if len(page_items) < 100:
                    break
                page += 1

            items_data = [item.model_dump() for item in all_items]

            # 3. 캐시 저장
            if items_data:
                from sqlalchemy.sql import func
                stmt = (
                    pg_insert(BidOpeningResult)
                    .values(bid_ntce_no=bidNtceNo, data=items_data)
                    .on_conflict_do_update(
                        index_elements=["bid_ntce_no"],
                        set_={"data": items_data, "fetched_at": func.now()},
                    )
                )
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to fetch bid results: {e}")
            items_data = []

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
