from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, nulls_last, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bid import BidNotice, BidOpeningResult
from app.models.user import User, UserBookmark
from app.schemas.user import (
    BookmarkListMeta,
    BookmarkResponse,
    PaginatedBookmarkResponse,
)

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
OPENING_RESULTS_TABLE = BidOpeningResult.__tablename__


def _now_kst_strs() -> tuple[str, str]:
    now = datetime.now(KST)
    return now.strftime("%Y%m%d%H%M"), now.strftime("%Y%m%d")


def _openg_completed_expr() -> Any:
    return and_(
        BidOpeningResult.bid_ntce_no.isnot(None),
        BidOpeningResult.data.isnot(None),
        func.jsonb_array_length(BidOpeningResult.data) > 0,
    )


def _not_completed_expr() -> Any:
    return or_(
        BidOpeningResult.bid_ntce_no.is_(None),
        BidOpeningResult.data.is_(None),
        func.jsonb_array_length(BidOpeningResult.data) == 0,
    )


def _status_filter(key: str, now_str: str, today_str: str) -> Any:
    not_done = _not_completed_expr()
    if key == "completed":
        return _openg_completed_expr()
    if key == "today":
        return and_(
            BidNotice.openg_dt.isnot(None),
            func.left(BidNotice.openg_dt, 8) == today_str,
            not_done,
        )
    if key == "upcoming":
        return and_(
            not_done,
            or_(
                BidNotice.openg_dt.is_(None),
                and_(
                    BidNotice.openg_dt > now_str,
                    func.left(BidNotice.openg_dt, 8) != today_str,
                ),
            ),
        )
    if key == "waiting":
        return and_(
            BidNotice.openg_dt.isnot(None),
            BidNotice.openg_dt <= now_str,
            func.left(BidNotice.openg_dt, 8) != today_str,
            not_done,
        )
    return None


def _joined_select(user_id: UUID, status: str):
    return (
        select(UserBookmark)
        .join(
            BidNotice,
            and_(
                BidNotice.bid_ntce_no == UserBookmark.bid_notice_no,
                BidNotice.bid_ntce_ord == func.coalesce(UserBookmark.bid_notice_ord, "000"),
            ),
            isouter=True,
        )
        .join(
            BidOpeningResult,
            and_(
                BidOpeningResult.bid_ntce_no == UserBookmark.bid_notice_no,
                BidOpeningResult.bid_ntce_ord == func.coalesce(UserBookmark.bid_notice_ord, "000"),
            ),
            isouter=True,
        )
        .where(
            UserBookmark.user_id == user_id,
            UserBookmark.status == status,
        )
    )


async def _get_counts(
    db: AsyncSession,
    user_id: UUID,
    status: str,
    now_str: str,
    today_str: str,
) -> dict[str, int]:
    if status != "bid_completed":
        cnt = (
            await db.execute(
                select(func.count()).select_from(
                    select(UserBookmark)
                    .where(
                        UserBookmark.user_id == user_id,
                        UserBookmark.status == status,
                    )
                    .subquery()
                )
            )
        ).scalar_one()
        return {"all": cnt}

    conds = {k: _status_filter(k, now_str, today_str) for k in ("today", "upcoming", "waiting", "completed")}
    stmt = _joined_select(user_id, status).with_only_columns(
        func.count(UserBookmark.bookmark_id).label("total"),
        func.count(case((conds["today"], 1))).label("today"),
        func.count(case((conds["upcoming"], 1))).label("upcoming"),
        func.count(case((conds["waiting"], 1))).label("waiting"),
        func.count(case((conds["completed"], 1))).label("completed"),
    ).order_by(None)
    row = (
        await db.execute(stmt)
    ).one()
    return {
        "all": row.total,
        "today": row.today,
        "upcoming": row.upcoming,
        "waiting": row.waiting,
        "completed": row.completed,
    }


def _sort_col(field: str) -> Any:
    return {
        "openg_dt": BidNotice.openg_dt,
        "bid_close_dt": BidNotice.bid_close_dt,
        "created_at": UserBookmark.created_at,
        "rank": UserBookmark.created_at,
    }.get(field, UserBookmark.created_at)


def _rank_order_sql(sort_dir: str) -> Any:
    data_ref = f"{OPENING_RESULTS_TABLE}.data"
    sql = f"""
        CASE
            WHEN :normalized_biz = '' OR {data_ref} IS NULL THEN NULL
            ELSE (
                WITH mine AS (
                    SELECT
                        CASE
                            WHEN NULLIF(BTRIM(e.value->>'opengRank'), '') ~ '^-?[0-9]+$'
                                THEN NULLIF(BTRIM(e.value->>'opengRank'), '')::integer
                            ELSE NULL
                        END AS rank_value,
                        CASE
                            WHEN NULLIF(e.value->>'bidprcrt', '') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                                THEN NULLIF(e.value->>'bidprcrt', '')::numeric
                            ELSE NULL
                        END AS bid_rate
                    FROM jsonb_array_elements({data_ref}) WITH ORDINALITY AS e(value, ord)
                    WHERE REPLACE(COALESCE(e.value->>'prcbdrBizno', ''), '-', '') = :normalized_biz
                    ORDER BY e.ord
                    LIMIT 1
                )
                SELECT
                    CASE
                        WHEN mine.rank_value IS NOT NULL THEN mine.rank_value
                        WHEN mine.bid_rate IS NOT NULL THEN -(
                            SELECT COUNT(*) + 1
                            FROM jsonb_array_elements({data_ref}) AS u(value)
                            WHERE NULLIF(BTRIM(COALESCE(u.value->>'opengRank', '')), '') IS NULL
                              AND CASE
                                    WHEN NULLIF(u.value->>'bidprcrt', '') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                                        THEN NULLIF(u.value->>'bidprcrt', '')::numeric
                                    ELSE NULL
                                  END > mine.bid_rate
                        )::integer
                        ELSE NULL
                    END
                FROM mine
            )
        END
    """
    if sort_dir == "asc":
        return text(sql + " ASC NULLS LAST")
    return text(sql + " DESC NULLS LAST")


def _enrich_one(
    b: UserBookmark,
    notice_map: dict[str, dict[str, str | None]],
    results_map: dict[str, dict[str, Any]],
    normalized_biz: str,
) -> BookmarkResponse:
    resp = BookmarkResponse.model_validate(b)
    result_key = f"{b.bid_notice_no}-{b.bid_notice_ord or '000'}"

    if b.bid_notice_no in notice_map:
        nd = notice_map[b.bid_notice_no]
        resp.bid_close_dt = nd["bid_close_dt"]
        resp.openg_dt = nd["openg_dt"]

    resp.openg_completed = result_key in results_map and results_map[result_key]["total"] > 0

    if (
        b.status == "bid_completed"
        and result_key in results_map
        and results_map[result_key]["total"] > 0
    ):
        cached = results_map[result_key]
        resp.total_bidders = cached["total"]

        if cached["data"]:
            for item in cached["data"]:
                if item.get("opengRank") == "1":
                    resp.winning_bid_price = item.get("bidprcAmt")
                    resp.winning_bid_rate = item.get("bidprcrt")
                    break

            if normalized_biz:
                unranked: list[tuple[float, str]] = []
                for r in cached["data"]:
                    rank_val = (r.get("opengRank") or "").strip()
                    if not rank_val:
                        try:
                            rate = float(r.get("bidprcrt") or "0")
                        except (ValueError, TypeError):
                            rate = 0.0
                        biz_r = (r.get("prcbdrBizno") or "").replace("-", "")
                        unranked.append((rate, biz_r))
                unranked.sort(key=lambda x: x[0], reverse=True)

                for item in cached["data"]:
                    biz = (item.get("prcbdrBizno") or "").replace("-", "")
                    if biz == normalized_biz:
                        resp.actual_bid_price = item.get("bidprcAmt")
                        resp.bid_rate = item.get("bidprcrt")
                        rank_val = (item.get("opengRank") or "").strip()
                        if rank_val:
                            resp.rank = rank_val
                        else:
                            for idx, (_, ubiz) in enumerate(unranked):
                                if ubiz == normalized_biz:
                                    resp.rank = str(-(idx + 1))
                                    break
                        break

    if resp.actual_bid_price is None and b.bid_price:
        resp.actual_bid_price = str(b.bid_price)

    return resp


async def get_paginated_bookmarks(
    db: AsyncSession,
    user: User,
    status: str,
    page: int,
    page_size: int,
    sort_field: str,
    sort_dir: str,
    openg_status: str | None,
) -> PaginatedBookmarkResponse:
    now_str, today_str = _now_kst_strs()

    counts = await _get_counts(db, user.user_id, status, now_str, today_str)

    # Build filtered + sorted paginated query
    stmt = _joined_select(user.user_id, status)

    if status == "bid_completed" and openg_status and openg_status != "all":
        filt = _status_filter(openg_status, now_str, today_str)
        if filt is not None:
            stmt = stmt.where(filt)

    if status == "bid_completed" and openg_status and openg_status != "all":
        filtered_total = counts.get(openg_status, 0)
    else:
        filtered_total = counts.get("all", 0)
    total_pages = max(1, math.ceil(filtered_total / page_size))
    page = min(page, total_pages)

    if sort_field == "rank":
        normalized_biz = (user.business_number or "").replace("-", "")
        stmt = stmt.params(normalized_biz=normalized_biz)
        stmt = stmt.order_by(_rank_order_sql(sort_dir), UserBookmark.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        bookmarks = (await db.execute(stmt)).scalars().all()
        page_items = await _enrich_bookmarks(db, bookmarks, user)
    else:
        col = _sort_col(sort_field)
        order = nulls_last(col.asc() if sort_dir == "asc" else col.desc())
        stmt = stmt.order_by(order, UserBookmark.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        bookmarks = (await db.execute(stmt)).scalars().all()
        page_items = await _enrich_bookmarks(db, bookmarks, user)

    return PaginatedBookmarkResponse(
        items=page_items,
        meta=BookmarkListMeta(
            total=filtered_total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            counts=counts,
        ),
    )


async def _enrich_bookmarks(
    db: AsyncSession,
    bookmarks: list[UserBookmark],
    user: User,
) -> list[BookmarkResponse]:
    bid_nos = [b.bid_notice_no for b in bookmarks]
    notice_map: dict[str, dict[str, str | None]] = {}
    results_map: dict[str, dict[str, Any]] = {}

    if bid_nos:
        notice_rows = await db.execute(
            select(BidNotice.bid_ntce_no, BidNotice.bid_close_dt, BidNotice.openg_dt)
            .where(BidNotice.bid_ntce_no.in_(bid_nos))
        )
        for row in notice_rows.all():
            notice_map[row[0]] = {"bid_close_dt": row[1], "openg_dt": row[2]}

        result_rows = await db.execute(
            select(BidOpeningResult).where(BidOpeningResult.bid_ntce_no.in_(bid_nos))
        )
        for row in result_rows.scalars().all():
            key = f"{row.bid_ntce_no}-{row.bid_ntce_ord}"
            results_map[key] = {
                "data": row.data or [],
                "total": len(row.data) if row.data else 0,
            }

    normalized_biz = ""
    if user.business_number:
        normalized_biz = user.business_number.replace("-", "")

    return [_enrich_one(b, notice_map, results_map, normalized_biz) for b in bookmarks]
