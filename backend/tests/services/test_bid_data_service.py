"""bid_data_service 회귀 테스트.

고정하는 핵심 동작:
  1. sync 엔트리 조회는 (시작, 끝) 두 컬럼을 모두 조건에 넣어야 한다.
     자정 시간별 윈도우와 일별 백필 윈도우는 sync_timestamp 가 같기 때문.
  2. 업종명 필터는 허용업종 정보가 매칭되는 공고만 남긴다.
     면허 정보가 없는 공고는 결과에서 제외한다 (엄격 필터).
     참가가능지역 필터는 "전체" sentinel 행이 있으므로 탈출구를 유지한다.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.models.bid import DataSyncLog
from app.schemas.bid import BidSearchParams
from app.services.bid_data_service import (
    BidDataService,
    escape_like,
    get_matching_regions,
    normalize_date_str,
    parse_price,
)


def compile_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def compile_sql_literal(stmt) -> str:
    """바인드 파라미터 값을 인라인으로 렌더링 (검색어 리터럴 검증용)."""
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def make_db(scalar_value=0, notices=None):
    """search_from_db 용 최소 mock 세션. 실행된 statement 를 기록합니다."""
    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar.return_value = scalar_value

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = notices or []

    db.execute = AsyncMock(side_effect=[count_result, rows_result])
    return db


@pytest.fixture
def service():
    return BidDataService()


# ---------------------------------------------------------------------------
# data_sync_log 윈도우 키
# ---------------------------------------------------------------------------

class TestSyncEntryLookup:
    def test_model_pk_includes_window_end(self):
        """window_end 가 PK 에 없으면 시간별/일별 윈도우가 서로를 덮어쓴다."""
        pk_cols = {c.name for c in DataSyncLog.__table__.primary_key.columns}
        assert pk_cols == {"sync_timestamp", "window_end"}

    @pytest.mark.asyncio
    async def test_get_sync_entry_filters_both_columns(self, service):
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock())

        await service.get_sync_entry(db, "202608040000", "202608040059")

        sql = compile_sql(db.execute.await_args.args[0])
        assert "sync_timestamp" in sql
        assert "window_end" in sql

    @pytest.mark.asyncio
    async def test_get_daily_sync_entry_uses_2359_window(self, service):
        captured = {}

        async def fake_get_sync_entry(db, sync_timestamp, window_end):
            captured["start"] = sync_timestamp
            captured["end"] = window_end
            return None

        service.get_sync_entry = fake_get_sync_entry
        await service.get_daily_sync_entry(MagicMock(), "20260804")

        assert captured["start"] == "202608040000"
        assert captured["end"] == "202608042359"

    @pytest.mark.asyncio
    async def test_daily_window_differs_from_midnight_hourly_window(self, service):
        """두 윈도우의 시작 시각은 같고 끝만 다르다 — 이것이 충돌의 원인이었다."""
        captured = {}

        async def fake_get_sync_entry(db, sync_timestamp, window_end):
            captured[window_end] = sync_timestamp
            return None

        service.get_sync_entry = fake_get_sync_entry
        await service.get_daily_sync_entry(MagicMock(), "20260804")

        assert captured["202608042359"] == "202608040000"
        # 자정 시간별 윈도우도 시작이 202608040000 이다.
        assert "202608040059" not in captured


# ---------------------------------------------------------------------------
# 검색 필터
# ---------------------------------------------------------------------------

class TestIndustryFilterStrict:
    @pytest.mark.asyncio
    async def test_industry_filter_excludes_notices_without_license_rows(
        self, service
    ):
        """허용업종 정보가 없는 공고는 업종 필터 결과에서 제외되어야 한다.

        '업종명' 필터는 해당 업종에 매칭되는 공고만 보여줘야 한다.
        면허 정보가 아예 없는 공고를 통과시키는 탈출구(NOT EXISTS)는 없어야 한다.
        (참가가능지역 필터는 "전체" sentinel 행이 있으므로 별개다)
        """
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            indstrytyNm="조경식재",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "bid_license_limits" in sql
        assert "NOT (EXISTS" not in sql, "면허 정보 없음 탈출구가 없어야 함"

    @pytest.mark.asyncio
    async def test_industry_filter_still_matches_by_name(self, service):
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            indstrytyNm="조경식재",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "lcns_lmt_nm" in sql
        assert "permsn_indstryty_list" in sql

    @pytest.mark.asyncio
    async def test_industry_filter_escapes_like_wildcards(self, service):
        """사용자 입력의 %, _ 는 리터럴로 취급해야 한다 (와일드카드 오동작 방지)."""
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            indstrytyNm="50%_A",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "ESCAPE" in sql.upper(), "ilike 에 escape 절이 있어야 함"

    @pytest.mark.asyncio
    async def test_industry_filter_splits_multiple_industries(self, service):
        """쉼표 구분 다중 업종은 각각 OR 로 결합되어야 한다."""
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            indstrytyNm="조경식재,토목",
        )

        await service.search_from_db(db, params)

        sql = compile_sql_literal(db.execute.await_args_list[1].args[0])
        assert "조경식재" in sql
        assert "토목" in sql

    @pytest.mark.asyncio
    async def test_blank_industry_filter_leaves_license_join_out(self, service):
        """공백만 입력되면 업종 필터를 적용하지 않는다 (모든 행 매칭 방지)."""
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            indstrytyNm="   ",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "bid_license_limits" not in sql

    @pytest.mark.asyncio
    async def test_no_industry_filter_leaves_license_join_out(self, service):
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "bid_license_limits" not in sql

    @pytest.mark.asyncio
    async def test_region_filter_keeps_notices_without_region_rows(self, service):
        """지역 필터에는 원래 탈출구가 있었다 — 회귀 방지용."""
        db = make_db()
        params = BidSearchParams(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            prtcptLmtRgnNm="경기도",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "NOT (EXISTS" in sql
        assert "bid_prtcpt_psbl_rgns" in sql

    @pytest.mark.asyncio
    async def test_openg_dt_filter_used_for_inqry_div_2(self, service):
        db = make_db()
        params = BidSearchParams(
            inqryDiv="2",
            inqryBgnDt="202608120000",
            inqryEndDt="202608122359",
        )

        await service.search_from_db(db, params)

        sql = compile_sql(db.execute.await_args_list[1].args[0])
        assert "openg_dt" in sql


# ---------------------------------------------------------------------------
# 순수 헬퍼
# ---------------------------------------------------------------------------

class TestHelpers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2026-08-04 16:35:07", "202608041635"),
            ("202608041635", "202608041635"),
            ("20260804", "202608040000"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalize_date_str(self, raw, expected):
        assert normalize_date_str(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("355098182", 355098182),
            ("355098182.0", 355098182),
            ("", 0),
            (None, 0),
            ("not-a-number", 0),
        ],
    )
    def test_parse_price(self, raw, expected):
        assert parse_price(raw) == expected

    def test_get_matching_regions_builds_prefix_chain(self):
        assert get_matching_regions("경기도 양평군") == [
            "전체",
            "",
            "경기도",
            "경기도 양평군",
        ]

    def test_get_matching_regions_single_token(self):
        assert get_matching_regions("경기도") == ["전체", "", "경기도"]

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("토목", "토목"),
            ("50%", "50\\%"),
            ("분야_A", "분야\\_A"),
            ("a\\b", "a\\\\b"),
            ("100%_B\\C", "100\\%\\_B\\\\C"),
        ],
    )
    def test_escape_like(self, raw, expected):
        assert escape_like(raw) == expected
