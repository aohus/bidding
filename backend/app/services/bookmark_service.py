from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, delete, func, nulls_last, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import BookmarkDashboardItem, UserBookmark
from app.schemas.user import (
    BookmarkListMeta,
    BookmarkResponse,
    PaginatedBookmarkResponse,
)

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def _normalize_bid_notice_ord(value: str | None) -> str:
    normalized = (value or "").strip()
    return normalized or "000"


def _now_kst_strs() -> tuple[str, str]:
    now = datetime.now(KST)
    return now.strftime("%Y%m%d%H%M"), now.strftime("%Y%m%d")



def _dashboard_response(row: BookmarkDashboardItem) -> BookmarkResponse:
    data = {
        field_name: getattr(row, field_name)
        for field_name in BookmarkResponse.model_fields
        if hasattr(row, field_name)
    }
    data["rank"] = str(row.rank_value) if row.rank_value is not None else None
    return BookmarkResponse(**data)


def _dashboard_sort_col(field: str) -> Any:
    return {
        "openg_dt": BookmarkDashboardItem.openg_dt,
        "bid_close_dt": BookmarkDashboardItem.bid_close_dt,
        "created_at": BookmarkDashboardItem.created_at,
        "rank": BookmarkDashboardItem.rank_value,
    }.get(field, BookmarkDashboardItem.created_at)


def _dashboard_status_filter(key: str, now_str: str, today_str: str) -> Any:
    not_done = BookmarkDashboardItem.openg_completed.is_(False)
    if key == "completed":
        return BookmarkDashboardItem.openg_completed.is_(True)
    if key == "today":
        return and_(
            BookmarkDashboardItem.openg_dt.isnot(None),
            func.left(BookmarkDashboardItem.openg_dt, 8) == today_str,
            not_done,
        )
    if key == "upcoming":
        return and_(
            not_done,
            or_(
                BookmarkDashboardItem.openg_dt.is_(None),
                and_(
                    BookmarkDashboardItem.openg_dt > now_str,
                    func.left(BookmarkDashboardItem.openg_dt, 8) != today_str,
                ),
            ),
        )
    if key == "waiting":
        return and_(
            BookmarkDashboardItem.openg_dt.isnot(None),
            BookmarkDashboardItem.openg_dt <= now_str,
            func.left(BookmarkDashboardItem.openg_dt, 8) != today_str,
            not_done,
        )
    return None


def _dashboard_bulk_upsert_sql(
    target_join_sql: str = "",
    where_sql: str = "",
    users_join_sql: str = "JOIN users u ON u.user_id = b.user_id",
    biz_val: str = "COALESCE(u.business_number, '')",
) -> str:
    return f"""
        INSERT INTO bookmark_dashboard_items (
            bookmark_id, user_id, bid_notice_no, bid_notice_ord,
            bid_notice_name, status, bid_price, notes, created_at, updated_at,
            bid_close_dt, openg_dt, openg_completed,
            actual_bid_price, bid_rate, rank_value, total_bidders,
            winning_bid_price, winning_bid_rate
        )
        SELECT
            b.bookmark_id,
            b.user_id,
            b.bid_notice_no,
            COALESCE(NULLIF(b.bid_notice_ord, ''), '000'),
            b.bid_notice_name,
            b.status,
            b.bid_price,
            b.notes,
            COALESCE(b.created_at, NOW()),
            b.updated_at,
            n.bid_close_dt,
            n.openg_dt,
            CASE
                WHEN r.data IS NOT NULL THEN jsonb_array_length(r.data) > 0
                ELSE false
            END,
            COALESCE(
                mine.value->>'bidprcAmt',
                CASE WHEN b.bid_price IS NOT NULL THEN b.bid_price::text ELSE NULL END
            ),
            mine.value->>'bidprcrt',
            CASE
                WHEN NULLIF(BTRIM(mine.value->>'opengRank'), '') ~ '^-?[0-9]+$'
                    THEN NULLIF(BTRIM(mine.value->>'opengRank'), '')::integer
                WHEN mine.value IS NOT NULL THEN -(
                    SELECT COUNT(*) + 1
                    FROM jsonb_array_elements(COALESCE(r.data, '[]'::jsonb)) AS unranked(value)
                    WHERE NULLIF(BTRIM(COALESCE(unranked.value->>'opengRank', '')), '') IS NULL
                      AND CASE
                            WHEN NULLIF(unranked.value->>'bidprcrt', '') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                                THEN NULLIF(unranked.value->>'bidprcrt', '')::numeric
                            ELSE NULL
                          END >
                          CASE
                            WHEN NULLIF(mine.value->>'bidprcrt', '') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                                THEN NULLIF(mine.value->>'bidprcrt', '')::numeric
                            ELSE NULL
                          END
                )::integer
                ELSE NULL
            END,
            CASE WHEN r.data IS NOT NULL THEN jsonb_array_length(r.data) ELSE NULL END,
            winner.value->>'bidprcAmt',
            winner.value->>'bidprcrt'
        FROM user_bookmarks b
        {target_join_sql}
        {users_join_sql}
        LEFT JOIN bid_notices n
          ON n.bid_ntce_no = b.bid_notice_no
         AND n.bid_ntce_ord = COALESCE(NULLIF(b.bid_notice_ord, ''), '000')
        LEFT JOIN bid_opening_results r
          ON r.bid_ntce_no = b.bid_notice_no
         AND r.bid_ntce_ord = COALESCE(NULLIF(b.bid_notice_ord, ''), '000')
        LEFT JOIN LATERAL (
            SELECT winner.value
            FROM jsonb_array_elements(COALESCE(r.data, '[]'::jsonb))
                 WITH ORDINALITY AS winner(value, ord)
            WHERE winner.value->>'opengRank' = '1'
            ORDER BY winner.ord
            LIMIT 1
        ) winner ON true
        LEFT JOIN LATERAL (
            SELECT mine.value
            FROM jsonb_array_elements(COALESCE(r.data, '[]'::jsonb))
                 WITH ORDINALITY AS mine(value, ord)
            WHERE NULLIF(REPLACE({biz_val}, '-', ''), '') IS NOT NULL
              AND REPLACE(COALESCE(mine.value->>'prcbdrBizno', ''), '-', '')
                  = REPLACE({biz_val}, '-', '')
            ORDER BY mine.ord
            LIMIT 1
        ) mine ON true
        {where_sql}
        ON CONFLICT (bookmark_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            bid_notice_no = EXCLUDED.bid_notice_no,
            bid_notice_ord = EXCLUDED.bid_notice_ord,
            bid_notice_name = EXCLUDED.bid_notice_name,
            status = EXCLUDED.status,
            bid_price = EXCLUDED.bid_price,
            notes = EXCLUDED.notes,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at,
            bid_close_dt = EXCLUDED.bid_close_dt,
            openg_dt = EXCLUDED.openg_dt,
            openg_completed = EXCLUDED.openg_completed,
            actual_bid_price = EXCLUDED.actual_bid_price,
            bid_rate = EXCLUDED.bid_rate,
            rank_value = EXCLUDED.rank_value,
            total_bidders = EXCLUDED.total_bidders,
            winning_bid_price = EXCLUDED.winning_bid_price,
            winning_bid_rate = EXCLUDED.winning_bid_rate
    """


async def _bulk_upsert_dashboard_items(
    db: AsyncSession,
    *,
    target_join_sql: str = "",
    where_sql: str = "",
    users_join_sql: str = "JOIN users u ON u.user_id = b.user_id",
    biz_val: str = "COALESCE(u.business_number, '')",
    params: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        text(_dashboard_bulk_upsert_sql(target_join_sql, where_sql, users_join_sql, biz_val)),
        params or {},
    )


async def upsert_bookmark_dashboard_item(
    db: AsyncSession,
    bookmark_id: UUID,
) -> None:
    await _bulk_upsert_dashboard_items(
        db,
        where_sql="WHERE b.bookmark_id = :bookmark_id",
        params={"bookmark_id": bookmark_id},
    )


async def delete_bookmark_dashboard_item(
    db: AsyncSession,
    bookmark_id: UUID,
) -> None:
    await db.execute(
        delete(BookmarkDashboardItem).where(
            BookmarkDashboardItem.bookmark_id == bookmark_id
        )
    )


async def refresh_dashboard_for_notice(
    db: AsyncSession,
    bid_notice_no: str,
    bid_notice_ord: str = "000",
) -> None:
    await refresh_dashboard_for_notices(db, [(bid_notice_no, bid_notice_ord)])


async def refresh_dashboard_for_notices(
    db: AsyncSession,
    notices: Iterable[tuple[str, str | None]],
) -> None:
    normalized_notices = sorted(
        {
            (bid_notice_no, _normalize_bid_notice_ord(bid_notice_ord))
            for bid_notice_no, bid_notice_ord in notices
            if bid_notice_no
        }
    )
    if not normalized_notices:
        return

    values_sql: list[str] = []
    params: dict[str, Any] = {}
    for idx, (bid_notice_no, bid_notice_ord) in enumerate(normalized_notices):
        no_key = f"bid_notice_no_{idx}"
        ord_key = f"bid_notice_ord_{idx}"
        values_sql.append(f"(:{no_key}, :{ord_key})")
        params[no_key] = bid_notice_no
        params[ord_key] = bid_notice_ord

    await _bulk_upsert_dashboard_items(
        db,
        target_join_sql=f"""
            JOIN (VALUES {', '.join(values_sql)})
                 AS target(bid_notice_no, bid_notice_ord)
              ON target.bid_notice_no = b.bid_notice_no
             AND target.bid_notice_ord = COALESCE(NULLIF(b.bid_notice_ord, ''), '000')
        """,
        params=params,
    )


async def refresh_dashboard_for_user(
    db: AsyncSession,
    user_id: UUID,
    business_number: str | None = None,
) -> None:
    if business_number is not None:
        await _bulk_upsert_dashboard_items(
            db,
            where_sql="WHERE b.user_id = :user_id",
            users_join_sql="",
            biz_val="COALESCE(:business_number, '')",
            params={"user_id": user_id, "business_number": business_number},
        )
    else:
        await _bulk_upsert_dashboard_items(
            db,
            where_sql="WHERE b.user_id = :user_id",
            params={"user_id": user_id},
        )


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
    if status == "bid_completed" and openg_status and openg_status != "all":
        status_filter = _dashboard_status_filter(openg_status, now_str, today_str)
    else:
        status_filter = None

    base_filters = [
        BookmarkDashboardItem.user_id == user.user_id,
        BookmarkDashboardItem.status == status,
    ]
    if status_filter is not None:
        base_filters.append(status_filter)

    if status == "bid_completed":
        status_exprs = {
            key: _dashboard_status_filter(key, now_str, today_str)
            for key in ("today", "upcoming", "waiting", "completed")
        }
        total_expr = func.count().label("total")
        rows = (
            await db.execute(
                select(
                    total_expr,
                    func.count(case((status_exprs["today"], 1))).label("today"),
                    func.count(case((status_exprs["upcoming"], 1))).label("upcoming"),
                    func.count(case((status_exprs["waiting"], 1))).label("waiting"),
                    func.count(case((status_exprs["completed"], 1))).label("completed"),
                )
                .where(
                    BookmarkDashboardItem.user_id == user.user_id,
                    BookmarkDashboardItem.status == status,
                )
            )
        ).one()
        counts = {
            "all": rows.total,
            "today": rows.today,
            "upcoming": rows.upcoming,
            "waiting": rows.waiting,
            "completed": rows.completed,
        }
    else:
        total = (
            await db.execute(
                select(func.count()).where(
                    BookmarkDashboardItem.user_id == user.user_id,
                    BookmarkDashboardItem.status == status,
                )
            )
        ).scalar_one()
        counts = {"all": total}

    filtered_total = counts.get(openg_status, 0) if status_filter is not None else counts["all"]
    total_pages = max(1, math.ceil(filtered_total / page_size))
    page = min(page, total_pages)

    col = _dashboard_sort_col(sort_field)
    order = nulls_last(col.asc() if sort_dir == "asc" else col.desc())
    stmt = (
        select(BookmarkDashboardItem)
        .where(*base_filters)
        .order_by(order, BookmarkDashboardItem.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    page_items = [_dashboard_response(row) for row in (await db.execute(stmt)).scalars().all()]

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
