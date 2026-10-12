"""external_bid_service 테스트.

고정하는 핵심 동작:
  1. 배치 내 PK 중복 제거 — PostgreSQL 은 하나의 ON CONFLICT DO UPDATE 에서
     같은 행을 두 번 건드리면 실패한다.
  2. notice_no 없는 레코드는 경고를 남기고 건너뛴다 (조용히 버리지 않는다).
  3. 조회는 전부 external_bid_* 테이블만 참조한다 — 나라장터 결과에 섞이지 않는다.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services.external_bid_service import (
    UPSERT_CHUNK_SIZE,
    ExternalBidService,
    _dedupe_by_pk,
)
from app.services.external_sources.mapping import NoticeRecord, ResultRecord


def compile_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def make_db(scalar_value=0, rows=None):
    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar.return_value = scalar_value
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = rows or []
    db.execute = AsyncMock(side_effect=[count_result, rows_result])
    db.commit = AsyncMock()
    return db


def make_write_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


def notice(notice_no="N1", ord_="000", source="kdhc", **kwargs) -> NoticeRecord:
    return NoticeRecord(
        source=source, notice_no=notice_no, notice_ord=ord_,
        data={"x": 1}, **kwargs,
    )


def result(notice_no="N1", seq=0, source="kra", **kwargs) -> ResultRecord:
    return ResultRecord(
        source=source, notice_no=notice_no, notice_ord="000", seq=seq,
        data={"x": 1}, **kwargs,
    )


@pytest.fixture
def service():
    return ExternalBidService()


# ---------------------------------------------------------------------------
# PK 중복 제거
# ---------------------------------------------------------------------------

class TestDedupeByPk:
    def test_keeps_last_occurrence(self):
        rows = [
            {"source": "a", "notice_no": "1", "notice_ord": "0", "title": "old"},
            {"source": "a", "notice_no": "1", "notice_ord": "0", "title": "new"},
        ]
        deduped = _dedupe_by_pk(rows, ("source", "notice_no", "notice_ord"))

        assert len(deduped) == 1
        assert deduped[0]["title"] == "new"

    def test_keeps_distinct_rows(self):
        rows = [
            {"source": "a", "notice_no": "1", "notice_ord": "0"},
            {"source": "a", "notice_no": "2", "notice_ord": "0"},
            {"source": "b", "notice_no": "1", "notice_ord": "0"},
        ]
        deduped = _dedupe_by_pk(rows, ("source", "notice_no", "notice_ord"))

        assert len(deduped) == 3

    def test_seq_distinguishes_results(self):
        rows = [
            {"source": "a", "notice_no": "1", "notice_ord": "0", "seq": 0},
            {"source": "a", "notice_no": "1", "notice_ord": "0", "seq": 1},
        ]
        deduped = _dedupe_by_pk(
            rows, ("source", "notice_no", "notice_ord", "seq")
        )

        assert len(deduped) == 2


# ---------------------------------------------------------------------------
# 저장
# ---------------------------------------------------------------------------

class TestSaveNotices:
    @pytest.mark.asyncio
    async def test_saves_and_commits(self, service):
        db = make_write_db()

        saved = await service.save_notices(db, [notice()])

        assert saved == 1
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_input_does_not_touch_db(self, service):
        db = make_write_db()

        assert await service.save_notices(db, []) == 0
        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_pk_in_batch_collapses(self, service):
        """같은 PK 두 건을 한 INSERT 에 넣으면 PostgreSQL 이 에러를 낸다."""
        db = make_write_db()

        saved = await service.save_notices(
            db, [notice(title="a"), notice(title="b")]
        )

        assert saved == 1

    @pytest.mark.asyncio
    async def test_skips_record_without_notice_no(self, service, caplog):
        db = make_write_db()

        with caplog.at_level(logging.WARNING):
            saved = await service.save_notices(
                db, [notice(notice_no=""), notice(notice_no="N2")]
            )

        assert saved == 1
        assert "empty notice_no" in caplog.text

    @pytest.mark.asyncio
    async def test_blank_notice_ord_defaults(self, service):
        db = make_write_db()

        await service.save_notices(db, [notice(ord_="")])

        stmt = db.execute.await_args.args[0]
        assert stmt.compile().params["notice_ord_m0"] == "000"

    @pytest.mark.asyncio
    async def test_upsert_updates_mutable_columns(self, service):
        db = make_write_db()

        await service.save_notices(db, [notice()])

        sql = compile_sql(db.execute.await_args.args[0])
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql
        for column in ("title", "status", "data", "fetched_at"):
            assert column in sql

    @pytest.mark.asyncio
    async def test_upsert_does_not_update_pk_columns(self, service):
        db = make_write_db()

        await service.save_notices(db, [notice()])

        sql = compile_sql(db.execute.await_args.args[0])
        update_clause = sql.split("DO UPDATE SET")[1]
        assert "source =" not in update_clause
        assert "notice_no =" not in update_clause

    @pytest.mark.asyncio
    async def test_chunks_large_batches(self, service):
        db = make_write_db()
        records = [
            notice(notice_no=f"N{i}") for i in range(UPSERT_CHUNK_SIZE + 5)
        ]

        saved = await service.save_notices(db, records)

        assert saved == UPSERT_CHUNK_SIZE + 5
        assert db.execute.await_count == 2


class TestSaveResults:
    @pytest.mark.asyncio
    async def test_saves_and_commits(self, service):
        db = make_write_db()

        saved = await service.save_results(db, [result()])

        assert saved == 1
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_same_notice_different_seq_both_kept(self, service):
        db = make_write_db()

        saved = await service.save_results(
            db, [result(seq=0, bidder_nm="A"), result(seq=1, bidder_nm="B")]
        )

        assert saved == 2

    @pytest.mark.asyncio
    async def test_empty_input_does_not_touch_db(self, service):
        db = make_write_db()

        assert await service.save_results(db, []) == 0
        db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 동기화 윈도우
# ---------------------------------------------------------------------------

class TestSyncWindow:
    @pytest.mark.asyncio
    async def test_get_sync_entry_filters_all_three_pk_columns(self, service):
        db = MagicMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=scalar_result)

        await service.get_sync_entry(db, "kdhc", "202610120000", "202610122359")

        sql = compile_sql(db.execute.await_args.args[0])
        assert "source" in sql
        assert "window_start" in sql
        assert "window_end" in sql

    @pytest.mark.asyncio
    async def test_mark_window_synced_upserts(self, service):
        db = make_write_db()

        await service.mark_window_synced(
            db, "kdhc", "202610120000", "202610122359", 3, 1
        )

        sql = compile_sql(db.execute.await_args.args[0])
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql
        db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 조회
# ---------------------------------------------------------------------------

class TestSearchNotices:
    @pytest.mark.asyncio
    async def test_queries_only_external_table(self, service):
        db = make_db()

        await service.search_notices(db)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "external_bid_notices" in sql
        # 나라장터 테이블이 섞이면 UI 노출 범위 약속이 깨진다.
        assert "bid_notices." not in sql.replace("external_bid_notices.", "")

    @pytest.mark.asyncio
    async def test_returns_rows_and_total(self, service):
        db = make_db(scalar_value=7, rows=["r1", "r2"])

        rows, total = await service.search_notices(db)

        assert rows == ["r1", "r2"]
        assert total == 7

    @pytest.mark.asyncio
    async def test_source_filter_accepts_csv(self, service):
        db = make_db()

        await service.search_notices(db, source="kdhc, kra")

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "IN (" in sql

    @pytest.mark.asyncio
    async def test_blank_source_is_ignored(self, service):
        db = make_db()

        await service.search_notices(db, source=" , ")

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "IN (" not in sql

    @pytest.mark.asyncio
    async def test_date_range_filters_on_rgst_dt(self, service):
        db = make_db()

        await service.search_notices(
            db, date_from="202610010000", date_to="202610122359"
        )

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert sql.count("rgst_dt") >= 2

    @pytest.mark.asyncio
    async def test_keyword_escapes_wildcards(self, service):
        db = make_db()

        await service.search_notices(db, keyword="100%_공사")

        stmt = db.execute.await_args_list[1].args[0]
        params = stmt.compile(dialect=postgresql.dialect()).params
        patterns = [v for v in params.values() if isinstance(v, str) and "%" in v]
        assert any("\\%" in p and "\\_" in p for p in patterns)

    @pytest.mark.asyncio
    async def test_pagination_offsets(self, service):
        db = make_db()

        await service.search_notices(db, page_no=3, num_of_rows=20)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "LIMIT" in sql and "OFFSET" in sql

    @pytest.mark.asyncio
    async def test_orders_by_rgst_dt_desc(self, service):
        db = make_db()

        await service.search_notices(db)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "ORDER BY" in sql and "DESC" in sql


class TestSearchResults:
    @pytest.mark.asyncio
    async def test_queries_results_table(self, service):
        db = make_db()

        await service.search_results(db)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "external_bid_results" in sql

    @pytest.mark.asyncio
    async def test_notice_no_filter(self, service):
        db = make_db()

        await service.search_results(db, notice_no="N1")

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "notice_no" in sql
