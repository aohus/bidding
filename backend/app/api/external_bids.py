"""외부기관(비-나라장터) 공고 조회 API.

기존 /bids/search 와 **완전히 별개 경로**다. 나라장터 검색 결과에 섞이지
않으므로 프론트엔드 변경 없이 데이터만 쌓인다.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_admin_user, get_current_user
from app.db.database import get_db
from app.models.external_bid import ExternalBidNotice, ExternalBidResult
from app.models.user import User
from app.schemas.external_bid import (
    ExternalBidItem,
    ExternalBidListResponse,
    ExternalBidResultItem,
    ExternalBidResultListResponse,
    ExternalSourceInfo,
    ExternalSourceListResponse,
)
from app.services.external_bid_service import external_bid_service
from app.services.external_sources.registry import SOURCES

logger = logging.getLogger(__name__)

# 프리픽스를 /bids 아래에 두지 않는다. bids 라우터에 /bids/{bidNtceNo}/results
# 같은 가변 경로가 있어서 /bids/external/results 가 bidNtceNo="external" 로
# 가로채진다. 등록 순서로 해결하면 라우터 순서를 바꾸는 순간 조용히 깨진다.
router = APIRouter(prefix="/external-bids", tags=["External Bid Notices"])

MAX_ROWS = 500


def _source_name(source_id: str) -> str:
    src = SOURCES.get(source_id)
    return src.name if src else source_id


def _to_item(row: ExternalBidNotice) -> ExternalBidItem:
    return ExternalBidItem(
        source=row.source,
        sourceName=_source_name(row.source),
        noticeNo=row.notice_no,
        noticeOrd=row.notice_ord,
        title=row.title,
        institution=row.institution,
        workDiv=row.work_div,
        cntrctMthd=row.cntrct_mthd,
        rgstDt=row.rgst_dt,
        bidCloseDt=row.bid_close_dt,
        opengDt=row.openg_dt,
        presmptPrce=row.presmpt_prce,
        status=row.status,
        raw=row.data or {},
    )


def _to_result_item(row: ExternalBidResult) -> ExternalBidResultItem:
    return ExternalBidResultItem(
        source=row.source,
        sourceName=_source_name(row.source),
        noticeNo=row.notice_no,
        noticeOrd=row.notice_ord,
        seq=row.seq,
        title=row.title,
        bidderNm=row.bidder_nm,
        bidderAmt=row.bidder_amt,
        statusNm=row.status_nm,
        opengDt=row.openg_dt,
        raw=row.data or {},
    )


def _validate_sources(source: Optional[str]) -> None:
    if not source:
        return
    unknown = [
        s.strip()
        for s in source.split(",")
        if s.strip() and s.strip() not in SOURCES
    ]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"알 수 없는 기관 식별자: {', '.join(unknown)} "
                f"(사용 가능: {', '.join(sorted(SOURCES))})"
            ),
        )


@router.get("/sources", response_model=ExternalSourceListResponse)
async def list_sources(
    current_user: User = Depends(get_current_user),
):
    """수집 대상 기관 목록."""
    return ExternalSourceListResponse(
        sources=[
            ExternalSourceInfo(
                source=src.source, name=src.name, granularity=src.granularity
            )
            for src in SOURCES.values()
        ]
    )


@router.get("", response_model=ExternalBidListResponse)
async def search_external_bids(
    source: Optional[str] = Query(
        None, description="기관 식별자 (쉼표로 복수 지정)"
    ),
    dateFrom: Optional[str] = Query(
        None, description="공고일시 시작 YYYYMMDDHHMM"
    ),
    dateTo: Optional[str] = Query(None, description="공고일시 끝 YYYYMMDDHHMM"),
    keyword: Optional[str] = Query(None, description="공고명/기관명 검색어"),
    pageNo: int = Query(1, ge=1),
    numOfRows: int = Query(100, ge=1, le=MAX_ROWS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """외부기관 입찰공고 목록 조회."""
    _validate_sources(source)

    rows, total = await external_bid_service.search_notices(
        db,
        source=source,
        date_from=dateFrom,
        date_to=dateTo,
        keyword=keyword,
        page_no=pageNo,
        num_of_rows=numOfRows,
    )
    return ExternalBidListResponse(
        items=[_to_item(row) for row in rows],
        totalCount=total,
        numOfRows=numOfRows,
        pageNo=pageNo,
    )


@router.get("/results", response_model=ExternalBidResultListResponse)
async def search_external_results(
    source: Optional[str] = Query(
        None, description="기관 식별자 (쉼표로 복수 지정)"
    ),
    noticeNo: Optional[str] = Query(None, description="공고번호"),
    pageNo: int = Query(1, ge=1),
    numOfRows: int = Query(100, ge=1, le=MAX_ROWS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """외부기관 낙찰/개찰 결과 조회."""
    _validate_sources(source)

    rows, total = await external_bid_service.search_results(
        db,
        source=source,
        notice_no=noticeNo,
        page_no=pageNo,
        num_of_rows=numOfRows,
    )
    return ExternalBidResultListResponse(
        items=[_to_result_item(row) for row in rows],
        totalCount=total,
        numOfRows=numOfRows,
        pageNo=pageNo,
    )


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_external_sync(
    source: str = Query(..., description="기관 식별자"),
    windowStart: str = Query(..., description="YYYYMMDDHHMM"),
    windowEnd: str = Query(..., description="YYYYMMDDHHMM"),
    admin_user: User = Depends(get_admin_user),
):
    """특정 기관/윈도우를 수동 동기화합니다 (관리자 전용)."""
    _validate_sources(source)

    from app.services.external_bid_sync_scheduler import (
        external_bid_sync_scheduler,
    )

    try:
        calls = await external_bid_sync_scheduler.sync_source_window(
            source, windowStart, windowEnd
        )
    except Exception as exc:
        logger.error(f"manual external sync failed [{source}]: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"동기화 실패: {exc}",
        )

    return {"source": source, "apiCalls": calls}
