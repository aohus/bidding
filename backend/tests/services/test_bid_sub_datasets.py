"""가산지역/공동도급의무지역/부공종/첨부파일 캐시 저장·조회·필터 테스트."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.bid import (
    BidSearchParams,
    IncntvRgnItem,
    JntcontrctDutyRgnItem,
    SubsiCnsttyItem,
)
from app.services.bid_data_service import BidDataService, location_matches


def sql_of(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def literal_sql_of(stmt) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


@pytest.fixture
def service():
    return BidDataService()


def new_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


def params_of(stmt) -> dict:
    return stmt.compile(dialect=postgresql.dialect()).params


# ---------------------------------------------------------------------------
# save_*
# ---------------------------------------------------------------------------

class TestSaveIncntv:
    @pytest.mark.asyncio
    async def test_upserts_rows_and_converts_sno(self, service):
        db = new_db()
        items = [
            IncntvRgnItem(bidNtceNo="R1", bidNtceOrd="001", sno="2", IncntvRgnNm="부산광역시")
        ]
        saved = await service.save_incntv_rgns(db, items)

        assert saved == 1
        stmt = db.execute.await_args.args[0]
        assert "ON CONFLICT" in sql_of(stmt)
        assert "DO UPDATE" in sql_of(stmt)
        p = params_of(stmt)
        assert p["sno"] == 2
        assert p["incntv_rgn_nm"] == "부산광역시"
        assert p["bid_ntce_ord"] == "001"
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_rows_without_bid_no(self, service):
        db = new_db()
        item = IncntvRgnItem(bidNtceNo="", bidNtceOrd="001", sno="1", IncntvRgnNm="x")
        assert await service.save_incntv_rgns(db, [item]) == 0
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bad_sno_uses_page_index_and_empty_ord_to_000(self, service):
        db = new_db()
        item = IncntvRgnItem(bidNtceNo="R1", bidNtceOrd="", sno="abc", IncntvRgnNm="x")
        await service.save_incntv_rgns(db, [item])
        p = params_of(db.execute.await_args.args[0])
        assert p["sno"] == 1
        assert p["bid_ntce_ord"] == "000"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [None, "", "abc"])
    async def test_unparsable_sno_rows_do_not_collapse(self, service, bad):
        """sno 가 없는 같은 공고의 여러 행이 sno=0 으로 합쳐지면 안 된다."""
        db = new_db()
        items = [
            IncntvRgnItem(bidNtceNo="R1", bidNtceOrd="000", sno=bad, IncntvRgnNm=n)
            for n in ("부산광역시", "대구광역시", "인천광역시")
        ]
        await service.save_incntv_rgns(db, items)
        snos = [params_of(c.args[0])["sno"] for c in db.execute.await_args_list]
        assert snos == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_page_index_fallback_for_other_datasets(self, service):
        db = new_db()
        await service.save_jntcontrct_duty_rgns(db, [
            JntcontrctDutyRgnItem(bidNtceNo="R1", bidNtceOrd="000", sno=None, JntcontrctDutyRgnNm="a"),
            JntcontrctDutyRgnItem(bidNtceNo="R1", bidNtceOrd="000", sno="x", JntcontrctDutyRgnNm="b"),
        ])
        await service.save_subsi_cnsttys(db, [
            SubsiCnsttyItem(bidNtceNo="R1", bidNtceOrd="000", sno=None, subsiCnsttyNm="a"),
            SubsiCnsttyItem(bidNtceNo="R1", bidNtceOrd="000", sno="7", subsiCnsttyNm="b"),
        ])
        snos = [params_of(c.args[0])["sno"] for c in db.execute.await_args_list]
        assert snos == [1, 2, 1, 7]

    @pytest.mark.asyncio
    async def test_empty_list(self, service):
        db = new_db()
        assert await service.save_incntv_rgns(db, []) == 0


class TestSaveJntcontrct:
    @pytest.mark.asyncio
    async def test_saves_rate_and_name(self, service):
        db = new_db()
        item = JntcontrctDutyRgnItem(
            bidNtceNo="R1", bidNtceOrd="000", sno="1",
            rgnDutyJntcontrctRt="49", JntcontrctDutyRgnNm="서울특별시",
        )
        assert await service.save_jntcontrct_duty_rgns(db, [item]) == 1
        stmt = db.execute.await_args.args[0]
        p = params_of(stmt)
        assert p["rgn_duty_jntcontrct_rt"] == "49"
        assert p["jntcontrct_duty_rgn_nm"] == "서울특별시"
        assert "DO UPDATE" in sql_of(stmt)


class TestSaveSubsi:
    @pytest.mark.asyncio
    async def test_saves_subsi(self, service):
        db = new_db()
        item = SubsiCnsttyItem(
            bidNtceNo="R1", bidNtceOrd="000", sno="3", subsiCnsttyCd="4992",
            subsiCnsttyNm="도장ㆍ습식ㆍ방수ㆍ석공사업", subsiCnsttyIndstrytyEvlRt="47",
        )
        assert await service.save_subsi_cnsttys(db, [item]) == 1
        stmt = db.execute.await_args.args[0]
        p = params_of(stmt)
        assert p["sno"] == 3
        assert p["subsi_cnstty_cd"] == "4992"
        assert p["subsi_cnstty_indstryty_evl_rt"] == "47"
        assert "DO UPDATE" in sql_of(stmt)


class TestMarkWindowSynced:
    @pytest.mark.asyncio
    async def test_new_counts_are_persisted(self, service):
        db = new_db()
        await service.mark_window_synced(
            db, "202611030000", "202611032359", 1, 2, 3,
            total_incntv_rgns=4, total_jntcontrct_duty_rgns=5, total_subsi_cnsttys=6,
        )
        p = params_of(db.execute.await_args.args[0])
        assert p["total_incntv_rgns"] == 4
        assert p["total_jntcontrct_duty_rgns"] == 5
        assert p["total_subsi_cnsttys"] == 6

    @pytest.mark.asyncio
    async def test_old_call_signature_still_works(self, service):
        db = new_db()
        await service.mark_window_synced(db, "a", "b", 1, 2)
        p = params_of(db.execute.await_args.args[0])
        assert p["total_incntv_rgns"] == 0


class TestSubDatasetsSyncedFlag:
    @pytest.mark.asyncio
    async def test_mark_window_persists_flag_default_false(self, service):
        db = new_db()
        await service.mark_window_synced(db, "a", "b", 1, 2)
        p = params_of(db.execute.await_args.args[0])
        assert p["sub_datasets_synced"] is False

    @pytest.mark.asyncio
    async def test_mark_window_persists_flag_true(self, service):
        db = new_db()
        await service.mark_window_synced(db, "a", "b", 1, 2, sub_datasets_synced=True)
        stmt = db.execute.await_args.args[0]
        assert params_of(stmt)["sub_datasets_synced"] is True
        assert "sub_datasets_synced=" in sql_of(stmt).replace(" ", "")

    @pytest.mark.asyncio
    async def test_list_pending_selects_only_daily_unsynced_recent(self, service):
        db = new_db()
        res = MagicMock()
        res.all.return_value = [("202611020000", "202611022359")]
        db.execute.return_value = res

        got = await service.list_windows_pending_sub_datasets(db, limit=5)

        assert got == [("202611020000", "202611022359")]
        sql = literal_sql_of(db.execute.await_args.args[0])
        assert "sub_datasets_synced IS false" in sql
        assert "LIKE '%%0000'" in sql and "LIKE '%%2359'" in sql
        assert "LIMIT 5" in sql
        assert "ORDER BY data_sync_log.sync_timestamp DESC" in sql

    @pytest.mark.asyncio
    async def test_mark_sub_datasets_synced_updates_flag_and_counts(self, service):
        db = new_db()
        await service.mark_sub_datasets_synced(db, "202611020000", "202611022359", 1, 2, 3)
        stmt = db.execute.await_args.args[0]
        assert sql_of(stmt).startswith("UPDATE data_sync_log")
        p = params_of(stmt)
        assert p["sub_datasets_synced"] is True
        assert (p["total_incntv_rgns"], p["total_jntcontrct_duty_rgns"],
                p["total_subsi_cnsttys"]) == (1, 2, 3)
        db.commit.assert_awaited_once()


class TestNoticeCreatedAt:
    @pytest.mark.asyncio
    async def test_upsert_never_touches_created_at(self, service):
        from app.schemas.bid import BidItem

        db = new_db()
        item = BidItem(bidNtceNo="R1", bidNtceOrd="000", bidNtceNm="n", ntceInsttNm="i")
        with patch("app.services.bookmark_service.refresh_dashboard_for_notices", AsyncMock()):
            await service.save_bid_notices(db, [item])
        stmt = db.execute.await_args_list[0].args[0]
        assert "created_at" not in sql_of(stmt)

    @pytest.mark.asyncio
    async def test_max_created_at(self, service):
        db = new_db()
        res = MagicMock()
        res.scalar.return_value = "T"
        db.execute.return_value = res
        assert await service.max_created_at(db, [("R1", "000")]) == "T"
        assert "max(bid_notices.created_at)" in sql_of(db.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_max_created_at_empty_keys_skips_query(self, service):
        db = new_db()
        assert await service.max_created_at(db, []) is None
        db.execute.assert_not_awaited()


class TestSearchCreatedAt:
    def _db(self):
        db = new_db()
        count = MagicMock()
        count.scalar.return_value = 0
        rows = MagicMock()
        rows.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[count, rows])
        return db

    PARAMS = BidSearchParams(inqryDiv="1", inqryBgnDt="202611010000", inqryEndDt="202611040000")

    @pytest.mark.asyncio
    async def test_created_after_filters_and_orders_asc(self, service):
        db = self._db()
        cutoff = datetime(2026, 11, 3, tzinfo=timezone.utc)
        await service.search_from_db(
            db, self.PARAMS, created_after=cutoff, order_by_created_at=True
        )
        sql = sql_of(db.execute.await_args_list[1].args[0])
        assert "bid_notices.created_at >" in sql
        assert "ORDER BY bid_notices.created_at ASC" in sql
        assert params_of(db.execute.await_args_list[1].args[0]) .get("created_at_1") == cutoff

    @pytest.mark.asyncio
    async def test_defaults_do_not_filter_on_created_at(self, service):
        db = self._db()
        await service.search_from_db(db, self.PARAMS)
        sql = sql_of(db.execute.await_args_list[1].args[0])
        assert "created_at >" not in sql
        assert "ORDER BY bid_notices.rgst_dt DESC" in sql


# ---------------------------------------------------------------------------
# attachment cache
# ---------------------------------------------------------------------------

def row_with(data, age: timedelta, kind="api"):
    return SimpleNamespace(
        data=data, fetched_at=datetime.now(timezone.utc) - age, kind=kind
    )


class TestAttachmentCache:
    @pytest.mark.asyncio
    async def test_miss_returns_none(self, service):
        db = new_db()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        db.execute.return_value = res
        assert await service.get_cached_attachments(db, "R1", "000") is None

    @pytest.mark.asyncio
    async def test_fresh_non_empty_hit(self, service):
        db = new_db()
        res = MagicMock()
        res.scalar_one_or_none.return_value = row_with([{"a": 1}], timedelta(hours=23))
        db.execute.return_value = res
        assert await service.get_cached_attachments(db, "R1", "000") == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_stale_non_empty_is_miss(self, service):
        db = new_db()
        res = MagicMock()
        res.scalar_one_or_none.return_value = row_with([{"a": 1}], timedelta(hours=25))
        db.execute.return_value = res
        assert await service.get_cached_attachments(db, "R1", "000") is None

    @pytest.mark.asyncio
    async def test_empty_fresh_hit_within_one_hour(self, service):
        db = new_db()
        res = MagicMock()
        res.scalar_one_or_none.return_value = row_with([], timedelta(minutes=30))
        db.execute.return_value = res
        assert await service.get_cached_attachments(db, "R1", "000") == []

    @pytest.mark.asyncio
    async def test_empty_stale_after_one_hour_is_miss(self, service):
        db = new_db()
        res = MagicMock()
        res.scalar_one_or_none.return_value = row_with([], timedelta(minutes=61))
        db.execute.return_value = res
        assert await service.get_cached_attachments(db, "R1", "000") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "kind,age,hit",
        [
            ("legacy", timedelta(minutes=59), True),
            ("legacy", timedelta(hours=2), False),  # 비어있지 않아도 1h TTL
            ("failed", timedelta(minutes=9), True),
            ("failed", timedelta(minutes=11), False),
            ("api", timedelta(hours=2), True),
        ],
    )
    async def test_ttl_depends_on_kind(self, service, kind, age, hit):
        db = new_db()
        res = MagicMock()
        res.scalar_one_or_none.return_value = row_with([{"a": 1}], age, kind)
        db.execute.return_value = res
        got = await service.get_cached_attachments(db, "R1", "000")
        assert (got is not None) is hit

    @pytest.mark.asyncio
    async def test_save_persists_kind(self, service):
        db = new_db()
        await service.save_attachments_cache(db, "R1", "000", [], kind="failed")
        assert params_of(db.execute.await_args.args[0])["kind"] == "failed"

    @pytest.mark.asyncio
    async def test_save_upserts(self, service):
        db = new_db()
        await service.save_attachments_cache(db, "R1", "001", [{"fileNm": "a"}])
        stmt = db.execute.await_args.args[0]
        assert "bid_attachments" in sql_of(stmt)
        assert "DO UPDATE" in sql_of(stmt)
        db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# location matching
# ---------------------------------------------------------------------------

class TestLocationMatches:
    def test_exact_parent_and_child(self):
        assert location_matches("경기도", "경기도 성남시")
        assert location_matches("경기도 성남시", "경기도 성남시")
        assert location_matches("경기도 성남시 분당구", "경기도 성남시")

    def test_zeonche_matches_all(self):
        assert location_matches("전체", "경기도 성남시")

    def test_other_region_does_not_match(self):
        assert not location_matches("부산광역시", "경기도 성남시")

    def test_prefix_without_space_does_not_match(self):
        assert not location_matches("경기도성남", "경기도 성남시")

    def test_empty_name_is_treated_as_not_match_for_sub_datasets(self):
        assert not location_matches(None, "경기도")


# ---------------------------------------------------------------------------
# enrichment
# ---------------------------------------------------------------------------

def make_notice(no="R1", ord_="000", **data):
    base = {"bidNtceNo": no, "bidNtceOrd": ord_, "bidNtceNm": "n", "ntceInsttNm": "i"}
    base.update(data)
    return SimpleNamespace(bid_ntce_no=no, bid_ntce_ord=ord_, data=base)


def dispatch_db(tables: dict):
    """실행된 statement 의 FROM 테이블명으로 결과 행을 돌려주는 mock 세션."""
    db = new_db()
    executed = []

    async def fake_execute(stmt, *a, **k):
        sql = sql_of(stmt)
        executed.append(sql)
        res = MagicMock()
        for table, rows in tables.items():
            if f"FROM {table}" in sql:
                res.all.return_value = rows
                return res
        res.all.return_value = []
        return res

    db.execute = AsyncMock(side_effect=fake_execute)
    db.executed = executed
    return db


class TestEnrichNotices:
    @pytest.mark.asyncio
    async def test_adds_sub_dataset_fields(self, service):
        db = dispatch_db({
            "bid_incntv_rgns": [("R1", "000", "부산광역시"), ("R1", "000", "경상남도")],
            "bid_jntcontrct_duty_rgns": [("R1", "000", "서울특별시", "49")],
            "bid_subsi_cnsttys": [
                ("R1", "000", 2, "전기공사업", "10"),
                ("R1", "000", 1, "도장공사업", "47"),
            ],
        })
        items = await service.enrich_notices(db, [make_notice()], None)
        it = items[0]
        assert it.incntvRgnNms == "경상남도, 부산광역시"
        assert it.jntcontrctDutyRgnNms == "서울특별시"
        assert it.rgnDutyJntcontrctRt == "49"
        assert [s.nm for s in it.subsiCnsttys] == ["도장공사업", "전기공사업"]
        assert it.subsiCnsttys[0].evlRt == "47"

    @pytest.mark.asyncio
    async def test_match_flags_none_without_location(self, service):
        db = dispatch_db({"bid_incntv_rgns": [("R1", "000", "부산광역시")]})
        it = (await service.enrich_notices(db, [make_notice()], None))[0]
        assert it.isIncntvRgnMatch is None
        assert it.isJntcontrctDutyRgnMatch is None

    @pytest.mark.asyncio
    async def test_match_flags_with_location(self, service):
        db = dispatch_db({
            "bid_incntv_rgns": [("R1", "000", "경기도")],
            "bid_jntcontrct_duty_rgns": [("R1", "000", "부산광역시", "30")],
        })
        it = (await service.enrich_notices(db, [make_notice()], "경기도 성남시"))[0]
        assert it.isIncntvRgnMatch is True
        assert it.isJntcontrctDutyRgnMatch is False

    @pytest.mark.asyncio
    async def test_no_sub_rows_is_false_with_location(self, service):
        db = dispatch_db({})
        it = (await service.enrich_notices(db, [make_notice()], "경기도"))[0]
        assert it.isIncntvRgnMatch is False
        assert it.incntvRgnNms == ""
        assert it.subsiCnsttys == []

    @pytest.mark.asyncio
    async def test_rate_falls_back_to_notice_data(self, service):
        db = dispatch_db({})
        notice = make_notice(rgnDutyJntcontrctRt="30")
        it = (await service.enrich_notices(db, [notice], None))[0]
        assert it.rgnDutyJntcontrctRt == "30"

    @pytest.mark.asyncio
    async def test_sub_table_rate_preferred_over_notice(self, service):
        db = dispatch_db({"bid_jntcontrct_duty_rgns": [("R1", "000", "서울특별시", "49")]})
        notice = make_notice(rgnDutyJntcontrctRt="30")
        it = (await service.enrich_notices(db, [notice], None))[0]
        assert it.rgnDutyJntcontrctRt == "49"

    @pytest.mark.asyncio
    async def test_keys_on_notice_order(self, service):
        db = dispatch_db({"bid_incntv_rgns": [("R1", "001", "부산광역시")]})
        n0 = make_notice("R1", "000")
        n1 = make_notice("R1", "001")
        items = await service.enrich_notices(db, [n0, n1], None)
        assert items[0].incntvRgnNms == ""
        assert items[1].incntvRgnNms == "부산광역시"

    @pytest.mark.asyncio
    async def test_batch_queries_do_not_scale_with_notices(self, service):
        db = dispatch_db({})
        await service.enrich_notices(
            db, [make_notice(f"R{i}") for i in range(50)], None
        )
        assert len(db.executed) <= 5

    @pytest.mark.asyncio
    async def test_empty_notices_no_queries(self, service):
        db = dispatch_db({})
        assert await service.enrich_notices(db, [], None) == []
        db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# search filters
# ---------------------------------------------------------------------------

def search_db(location_name=None):
    """search_from_db 용 mock: user_location 조회 → count → rows."""
    db = new_db()
    loc_res = MagicMock()
    loc_res.scalar_one_or_none.return_value = (
        SimpleNamespace(location_name=location_name) if location_name else None
    )
    count_res = MagicMock()
    count_res.scalar.return_value = 0
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = []

    async def fake_execute(stmt, *a, **k):
        sql = sql_of(stmt)
        if "FROM user_locations" in sql:
            return loc_res
        if "count(" in sql.lower():
            return count_res
        return rows_res

    db.execute = AsyncMock(side_effect=fake_execute)
    return db


def notice_query_sql(db) -> str:
    for call in db.execute.await_args_list:
        sql = sql_of(call.args[0])
        if "FROM bid_notices" in sql and "count(" not in sql.lower():
            return sql
    raise AssertionError("no notice query")


def base_params(**kw):
    return BidSearchParams(
        inqryDiv="1", inqryBgnDt="202611010000", inqryEndDt="202611032359", **kw
    )


class TestNewSearchFilters:
    @pytest.mark.asyncio
    async def test_incntv_only_with_location_adds_exists(self, service):
        db = search_db("경기도 성남시")
        await service.search_from_db(db, base_params(incntvRgnOnly=True), user_id="u")
        sql = notice_query_sql(db)
        assert "bid_incntv_rgns" in sql
        assert "EXISTS" in sql

    @pytest.mark.asyncio
    async def test_jntcontrct_only_with_location_adds_exists(self, service):
        db = search_db("경기도")
        await service.search_from_db(db, base_params(jntcontrctDutyRgnOnly=True), user_id="u")
        assert "bid_jntcontrct_duty_rgns" in notice_query_sql(db)

    @pytest.mark.asyncio
    async def test_region_filter_ignored_without_location(self, service, caplog):
        db = search_db(None)
        with caplog.at_level("INFO"):
            await service.search_from_db(
                db, base_params(incntvRgnOnly=True, jntcontrctDutyRgnOnly=True), user_id="u"
            )
        sql = notice_query_sql(db)
        assert "bid_incntv_rgns" not in sql
        assert "bid_jntcontrct_duty_rgns" not in sql
        assert any("incntv" in r.message.lower() or "location" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_region_filter_ignored_for_anonymous(self, service):
        db = search_db(None)
        await service.search_from_db(db, base_params(incntvRgnOnly=True), user_id=None)
        assert "bid_incntv_rgns" not in notice_query_sql(db)

    @pytest.mark.asyncio
    async def test_region_filter_values_are_parameterized(self, service):
        db = search_db("경기도 성남시")
        await service.search_from_db(db, base_params(incntvRgnOnly=True), user_id="u")
        sql = notice_query_sql(db)
        assert "경기도" not in sql

    @pytest.mark.asyncio
    async def test_industry_with_subsi_is_or(self, service):
        db = search_db(None)
        await service.search_from_db(
            db, base_params(indstrytyNm="도장", includeSubsiCnstty=True)
        )
        sql = notice_query_sql(db)
        assert "bid_license_limits" in sql
        assert "bid_subsi_cnsttys" in sql
        assert "subsi_cnstty_nm ILIKE" in sql
        assert ") OR (EXISTS" in sql.replace("\n", "") or "OR (EXISTS" in sql.replace("\n", "") or "OR EXISTS" in sql.replace("\n", "")

    @pytest.mark.asyncio
    async def test_industry_without_flag_has_no_subsi(self, service):
        db = search_db(None)
        await service.search_from_db(db, base_params(indstrytyNm="도장"))
        assert "bid_subsi_cnsttys" not in notice_query_sql(db)

    @pytest.mark.asyncio
    async def test_subsi_flag_without_industry_is_noop(self, service):
        db = search_db(None)
        await service.search_from_db(db, base_params(includeSubsiCnstty=True))
        assert "bid_subsi_cnsttys" not in notice_query_sql(db)

    @pytest.mark.asyncio
    async def test_subsi_escapes_like(self, service):
        db = search_db(None)
        await service.search_from_db(
            db, base_params(indstrytyNm="50%", includeSubsiCnstty=True)
        )
        stmt = next(
            c.args[0] for c in db.execute.await_args_list
            if "FROM bid_notices" in sql_of(c.args[0]) and "count(" not in sql_of(c.args[0]).lower()
        )
        assert "50\\\\%" in literal_sql_of(stmt)
