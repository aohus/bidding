"""외부기관 공고/결과 영속화 + 동기화 윈도우 기록.

bid_data_service(나라장터) 와 독립이다. 동기화 마킹 원칙만 동일하게 따른다:
**API 호출이 하나라도 실패한 윈도우는 마킹하지 않는다** — 마킹하면 그 구간이
영구 누락된다.
"""

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_bid import (
    ExternalBidNotice,
    ExternalBidResult,
    ExternalSyncLog,
)
from app.services.external_sources.mapping import NoticeRecord, ResultRecord

logger = logging.getLogger(__name__)

# 한 INSERT 에 넣는 최대 행 수. 파라미터 수 상한(65535)과 JSONB 크기를 고려.
UPSERT_CHUNK_SIZE = 200

_NOTICE_PK = ("source", "notice_no", "notice_ord")
_RESULT_PK = ("source", "notice_no", "notice_ord", "seq")


def _chunks(rows: Sequence[dict], size: int) -> Iterable[Sequence[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _dedupe_by_pk(rows: List[dict], pk_fields: Tuple[str, ...]) -> List[dict]:
    """배치 내 PK 중복을 제거합니다 (뒤에 온 값이 이김).

    PostgreSQL 은 하나의 INSERT ... ON CONFLICT DO UPDATE 에서 같은 행을 두 번
    건드리면 "cannot affect row a second time" 로 실패한다. 소스가 같은 공고를
    두 번 내려보내는 경우(마사회 재공고, 수자원 월 중복 등)에 실제로 터진다.
    """
    merged: Dict[tuple, dict] = {}
    for row in rows:
        merged[tuple(row[field] for field in pk_fields)] = row
    return list(merged.values())


class ExternalBidService:
    """외부기관 데이터 저장/조회."""

    # -- 저장 ---------------------------------------------------------------

    async def save_notices(
        self, db: AsyncSession, records: Sequence[NoticeRecord]
    ) -> int:
        """공고를 upsert 합니다. 저장된 행 수를 반환합니다."""
        rows = [
            self._notice_row(record)
            for record in records
            if self._has_key(record, "notice")
        ]
        if not rows:
            return 0

        rows = _dedupe_by_pk(rows, _NOTICE_PK)
        mutable = (
            "title", "institution", "work_div", "cntrct_mthd", "rgst_dt",
            "bid_close_dt", "openg_dt", "presmpt_prce", "status", "data",
        )
        await self._upsert(db, ExternalBidNotice, rows, _NOTICE_PK, mutable)
        await db.commit()
        logger.info(f"saved {len(rows)} external bid notices")
        return len(rows)

    async def save_results(
        self, db: AsyncSession, records: Sequence[ResultRecord]
    ) -> int:
        """낙찰/결과를 upsert 합니다. 저장된 행 수를 반환합니다."""
        rows = [
            self._result_row(record)
            for record in records
            if self._has_key(record, "result")
        ]
        if not rows:
            return 0

        rows = _dedupe_by_pk(rows, _RESULT_PK)
        mutable = (
            "title", "bidder_nm", "bidder_amt", "status_nm", "openg_dt", "data",
        )
        await self._upsert(db, ExternalBidResult, rows, _RESULT_PK, mutable)
        await db.commit()
        logger.info(f"saved {len(rows)} external bid results")
        return len(rows)

    @staticmethod
    def _has_key(record: Any, kind: str) -> bool:
        """PK 를 만들 수 없는 레코드를 걸러냅니다 (조용히 버리지 않고 경고)."""
        if record.notice_no:
            return True
        logger.warning(
            f"skipping external bid {kind} with empty notice_no "
            f"(source={record.source}, title={record.title!r})"
        )
        return False

    @staticmethod
    def _notice_row(record: NoticeRecord) -> dict:
        return {
            "source": record.source,
            "notice_no": record.notice_no,
            "notice_ord": record.notice_ord or "000",
            "title": record.title,
            "institution": record.institution,
            "work_div": record.work_div,
            "cntrct_mthd": record.cntrct_mthd,
            "rgst_dt": record.rgst_dt,
            "bid_close_dt": record.bid_close_dt,
            "openg_dt": record.openg_dt,
            "presmpt_prce": record.presmpt_prce,
            "status": record.status,
            "data": record.data,
        }

    @staticmethod
    def _result_row(record: ResultRecord) -> dict:
        return {
            "source": record.source,
            "notice_no": record.notice_no,
            "notice_ord": record.notice_ord or "000",
            "seq": record.seq,
            "title": record.title,
            "bidder_nm": record.bidder_nm,
            "bidder_amt": record.bidder_amt,
            "status_nm": record.status_nm,
            "openg_dt": record.openg_dt,
            "data": record.data,
        }

    @staticmethod
    async def _upsert(
        db: AsyncSession,
        model: Any,
        rows: Sequence[dict],
        pk_fields: Tuple[str, ...],
        mutable_fields: Tuple[str, ...],
    ) -> None:
        for chunk in _chunks(rows, UPSERT_CHUNK_SIZE):
            stmt = insert(model).values(list(chunk))
            stmt = stmt.on_conflict_do_update(
                index_elements=list(pk_fields),
                set_={
                    field: getattr(stmt.excluded, field)
                    for field in mutable_fields
                }
                | {"fetched_at": func.now()},
            )
            await db.execute(stmt)

    # -- 동기화 윈도우 -------------------------------------------------------

    async def get_sync_entry(
        self,
        db: AsyncSession,
        source: str,
        window_start: str,
        window_end: str,
    ) -> Optional[ExternalSyncLog]:
        result = await db.execute(
            select(ExternalSyncLog).where(
                ExternalSyncLog.source == source,
                ExternalSyncLog.window_start == window_start,
                ExternalSyncLog.window_end == window_end,
            )
        )
        return result.scalar_one_or_none()

    async def mark_window_synced(
        self,
        db: AsyncSession,
        source: str,
        window_start: str,
        window_end: str,
        total_notices: int,
        total_results: int,
    ) -> None:
        stmt = (
            insert(ExternalSyncLog)
            .values(
                source=source,
                window_start=window_start,
                window_end=window_end,
                total_notices=total_notices,
                total_results=total_results,
            )
            .on_conflict_do_update(
                index_elements=["source", "window_start", "window_end"],
                set_={
                    "synced_at": func.now(),
                    "total_notices": total_notices,
                    "total_results": total_results,
                },
            )
        )
        await db.execute(stmt)
        await db.commit()

    # -- 조회 ---------------------------------------------------------------

    async def search_notices(
        self,
        db: AsyncSession,
        source: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        keyword: Optional[str] = None,
        page_no: int = 1,
        num_of_rows: int = 100,
    ) -> Tuple[List[ExternalBidNotice], int]:
        """외부기관 공고를 조회합니다. (행 목록, 전체 건수)

        기존 /bids/search 와 완전히 별개 경로다 — 나라장터 결과에 섞이지 않는다.
        """
        query = select(ExternalBidNotice)
        query = self._apply_filters(query, source, date_from, date_to, keyword)

        count_query = select(func.count()).select_from(
            query.with_only_columns(ExternalBidNotice.notice_no).subquery()
        )
        total = (await db.execute(count_query)).scalar() or 0

        query = query.order_by(ExternalBidNotice.rgst_dt.desc())
        query = query.offset((page_no - 1) * num_of_rows).limit(num_of_rows)

        rows = (await db.execute(query)).scalars().all()
        return list(rows), total

    @staticmethod
    def _apply_filters(
        query: Any,
        source: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        keyword: Optional[str],
    ) -> Any:
        if source:
            sources = [s.strip() for s in source.split(",") if s.strip()]
            if sources:
                query = query.where(ExternalBidNotice.source.in_(sources))
        if date_from:
            query = query.where(ExternalBidNotice.rgst_dt >= date_from)
        if date_to:
            query = query.where(ExternalBidNotice.rgst_dt <= date_to)
        if keyword:
            # 사용자 입력의 와일드카드를 리터럴로 취급한다.
            escaped = (
                keyword.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    ExternalBidNotice.title.ilike(pattern, escape="\\"),
                    ExternalBidNotice.institution.ilike(pattern, escape="\\"),
                )
            )
        return query

    async def search_results(
        self,
        db: AsyncSession,
        source: Optional[str] = None,
        notice_no: Optional[str] = None,
        page_no: int = 1,
        num_of_rows: int = 100,
    ) -> Tuple[List[ExternalBidResult], int]:
        """외부기관 낙찰/결과를 조회합니다. (행 목록, 전체 건수)"""
        query = select(ExternalBidResult)
        if source:
            sources = [s.strip() for s in source.split(",") if s.strip()]
            if sources:
                query = query.where(ExternalBidResult.source.in_(sources))
        if notice_no:
            query = query.where(ExternalBidResult.notice_no == notice_no)

        count_query = select(func.count()).select_from(
            query.with_only_columns(ExternalBidResult.notice_no).subquery()
        )
        total = (await db.execute(count_query)).scalar() or 0

        query = query.order_by(ExternalBidResult.openg_dt.desc())
        query = query.offset((page_no - 1) * num_of_rows).limit(num_of_rows)

        rows = (await db.execute(query)).scalars().all()
        return list(rows), total


external_bid_service = ExternalBidService()
