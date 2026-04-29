"""Reserve-price (예정가격) backfill helpers.

CLI 스크립트와 배포 시 startup 훅이 함께 사용합니다.

핵심 흐름:
    1. `bid_notices.openg_dt` 가 [from, to] 범위인 공고 중
       `bid_reserve_prices` 미수집 row 를 batch 로 수집
    2. 각 row 별로 `narajangter.get_reserve_price()` 호출 → upsert
    3. 완료 후 `REFRESH MATERIALIZED VIEW [CONCURRENTLY] mv_estimate_rate_stats`
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import and_, exists, func, select, text, tuple_

from app.db.database import AsyncSessionLocal
from app.models.bid import BidBasisAmount, BidNotice, BidReservePrice
from app.services.bid_data_service import bid_data_service
from app.services.narajangter import narajangter_service

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 200
DEFAULT_INTER_CALL_SLEEP = 0.5


async def fetch_reserve_price_with_fallback(
    bid_ntce_no: str,
    bid_ntce_ord: Optional[str],
    hint_type: str,
) -> tuple[Optional[dict], str, int]:
    """hint_type 우선 시도, None 응답이면 다른 type 자동 시도.

    Returns: (item, used_type, calls_made)
    item is None 이면 두 type 모두 빈 응답 (저장 skip 필요).
    calls_made 는 실제 외부 API 호출 횟수 (1 또는 2).
    """
    primary = hint_type if hint_type in ("cnstwk", "servc") else "cnstwk"
    secondary = "servc" if primary == "cnstwk" else "cnstwk"

    item = await narajangter_service.get_reserve_price(
        bidNtceNo=bid_ntce_no, bid_type=primary, bidNtceOrd=bid_ntce_ord or None
    )
    if item is not None:
        return item, primary, 1

    await asyncio.sleep(DEFAULT_INTER_CALL_SLEEP)
    item = await narajangter_service.get_reserve_price(
        bidNtceNo=bid_ntce_no, bid_type=secondary, bidNtceOrd=bid_ntce_ord or None
    )
    return item, secondary, 2


async def _list_pending_in_range(
    window_from: str,
    window_to: str,
    limit: int,
    cursor: Optional[tuple[str, str, str]] = None,
) -> list[tuple[str, str, str, str]]:
    """openg_dt 가 [from, to] 인 미수집 공고 N건을 반환.

    cursor: (openg_dt, bid_ntce_no, bid_ntce_ord) — 이 값보다 더 오래된 row 만 조회.
    Returns: list of (bid_ntce_no, bid_ntce_ord, bid_type, openg_dt)
    """
    async with AsyncSessionLocal() as db:
        query = (
            select(
                BidNotice.bid_ntce_no,
                BidNotice.bid_ntce_ord,
                func.coalesce(BidBasisAmount.bid_type, "cnstwk"),
                BidNotice.openg_dt,
            )
            .outerjoin(
                BidBasisAmount,
                and_(
                    BidBasisAmount.bid_ntce_no == BidNotice.bid_ntce_no,
                    BidBasisAmount.bid_ntce_ord == BidNotice.bid_ntce_ord,
                ),
            )
            .where(
                BidNotice.openg_dt.isnot(None),
                BidNotice.openg_dt != "",
                BidNotice.openg_dt >= window_from,
                BidNotice.openg_dt <= window_to,
                ~exists().where(
                    and_(
                        BidReservePrice.bid_ntce_no == BidNotice.bid_ntce_no,
                        BidReservePrice.bid_ntce_ord == BidNotice.bid_ntce_ord,
                    )
                ),
            )
        )
        if cursor is not None:
            last_dt, last_no, last_ord = cursor
            query = query.where(
                tuple_(
                    BidNotice.openg_dt,
                    BidNotice.bid_ntce_no,
                    BidNotice.bid_ntce_ord,
                )
                < tuple_(last_dt, last_no, last_ord)
            )
        query = query.order_by(
            BidNotice.openg_dt.desc(),
            BidNotice.bid_ntce_no.desc(),
            BidNotice.bid_ntce_ord.desc(),
        ).limit(limit)
        result = await db.execute(query)
        return [(r[0], r[1], r[2], r[3]) for r in result.all()]


async def backfill_reserve_prices(
    window_from: str,
    window_to: str,
    *,
    max_calls: Optional[int] = None,
    inter_call_sleep: float = DEFAULT_INTER_CALL_SLEEP,
    refresh_after: bool = True,
    refresh_concurrently: bool = True,
) -> dict[str, int]:
    """범위 내 reserve_price 를 모두 백필 후 mv 를 REFRESH 합니다.

    Args:
        window_from / window_to: YYYYMMDD 또는 YYYYMMDDHHMM (string compare)
        max_calls: API 호출 상한 (None=제한 없음)
        refresh_after: 백필 후 mv 자동 REFRESH 여부

    Returns:
        {"fetched": N, "saved": M, "errors": K}
    """
    fetched = 0
    saved = 0
    errors = 0
    # YYYYMMDDHHMM 길이로 정규화
    norm_from = (window_from + "0000")[:12]
    norm_to = (window_to + "2359")[:12]
    logger.info(f"reserve_price backfill: {norm_from} ~ {norm_to}")

    # cursor 기반 페이지네이션: saved 여부와 무관하게 더 오래된 row 로 진행.
    # None 응답이어도 cursor 가 진행되므로 무한루프 없이 범위 전체를 시도한다.
    last_cursor: Optional[tuple[str, str, str]] = None
    last_progress_log = 0
    while True:
        if max_calls is not None and fetched >= max_calls:
            logger.info("reserve_price backfill: max_calls reached")
            break
        targets = await _list_pending_in_range(
            norm_from, norm_to, limit=DEFAULT_BATCH_SIZE, cursor=last_cursor
        )
        if not targets:
            logger.info("reserve_price backfill: no more pending targets, done")
            break

        for bid_no, bid_ord, bid_type, _openg_dt in targets:
            if max_calls is not None and fetched >= max_calls:
                break
            try:
                item, used_type, calls_made = await fetch_reserve_price_with_fallback(
                    bid_no, bid_ord, bid_type
                )
                fetched += calls_made
                if item is not None:
                    async with AsyncSessionLocal() as db:
                        if await bid_data_service.save_reserve_price(
                            db, bid_no, bid_ord or "000", used_type, item
                        ):
                            saved += 1
                if fetched - last_progress_log >= 20:
                    logger.info(
                        f"reserve_price backfill progress: fetched={fetched}, saved={saved}"
                    )
                    last_progress_log = fetched
            except Exception as exc:
                errors += 1
                logger.warning(
                    f"reserve_price backfill failed {bid_no}-{bid_ord} ({bid_type}): {exc}"
                )
            await asyncio.sleep(inter_call_sleep)

        # 다음 batch 를 위해 cursor 를 마지막 row 로 갱신.
        # saved 여부와 무관하게 진행하므로 일시 장애에도 더 오래된 row 가 시도된다.
        last_target = targets[-1]
        last_cursor = (last_target[3], last_target[0], last_target[1])

    if refresh_after:
        await refresh_estimate_rate_stats(concurrently=refresh_concurrently)

    logger.info(
        f"reserve_price backfill complete: fetched={fetched}, saved={saved}, errors={errors}"
    )
    return {"fetched": fetched, "saved": saved, "errors": errors}


async def refresh_estimate_rate_stats(*, concurrently: bool = True) -> None:
    """mv_estimate_rate_stats 를 REFRESH 합니다."""
    sql = (
        "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_estimate_rate_stats"
        if concurrently
        else "REFRESH MATERIALIZED VIEW mv_estimate_rate_stats"
    )
    async with AsyncSessionLocal() as db:
        await db.execute(text(sql))
        await db.commit()
    logger.info(f"mv_estimate_rate_stats refreshed (concurrently={concurrently})")
