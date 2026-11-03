"""이메일 알림 스케줄러 회귀 테스트.

고정하는 핵심 동작:
  1. 저장된 검색 조건(search_conditions)을 BidSearchParams 로 화이트리스트 매핑
  2. 외부 API 가 아닌 DB(search_from_db)로 조회
  3. 윈도우는 KST 기준, 직전 알림 이후 구간만 (실행 간 중복 발송 없음)
  4. 발송 성공 후에만 last_notification_at 갱신/커밋
  5. 한 사용자의 실패가 다른 사용자에게 영향 주지 않음
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.bid import BidApiResponse, BidItem
from app.services.scheduler import NotificationScheduler, _str_list, build_search_params

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 3, 12, 30, 45, tzinfo=KST)
COND = {"industries": ["토목공사업"]}
CREATED = datetime(2026, 11, 3, 12, 20, 11, 123456, tzinfo=KST)


def make_pref(conditions=None, frequency="daily", last=None, enabled=True):
    return SimpleNamespace(
        search_conditions={} if conditions is None else conditions,
        notification_frequency=frequency,
        last_notification_at=last,
        email_notifications_enabled=enabled,
    )


def make_user(name="u"):
    return SimpleNamespace(user_id=uuid.uuid4(), username=name, email=f"{name}@x.kr")


def make_bid(no="R1"):
    return BidItem(bidNtceNo=no, bidNtceOrd="000", bidNtceNm="공고", ntceInsttNm="기관")


def response(items):
    return BidApiResponse(items=items, totalCount=len(items), numOfRows=100, pageNo=1)


@pytest.fixture
def db():
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def sched():
    return NotificationScheduler()


@pytest.fixture
def mocks():
    with patch("app.services.scheduler.bid_data_service") as bds, patch(
        "app.services.scheduler.email_service"
    ) as email:
        bds.search_from_db = AsyncMock(return_value=response([make_bid()]))
        bds.max_created_at = AsyncMock(return_value=CREATED)
        email.send_bid_notification = AsyncMock(return_value=True)
        yield SimpleNamespace(bds=bds, email=email)


# ---------------------------------------------------------------------------
# 조건 -> 파라미터 매핑
# ---------------------------------------------------------------------------

class TestBuildSearchParams:
    def test_maps_frontend_saved_keys(self):
        conditions = {
            "inqryDiv": "2",
            "regions": ["서울특별시", " 경기도 "],
            "cnstrtsiteRgnNm": "강남",
            "industries": ["토목공사업", "건축공사업"],
            "priceStart": "1000000",
            "priceEnd": "500000000",
            "excludeClosed": "Y",
            "useLocationFilter": True,
            "incntvRgnOnly": True,
            "jntcontrctDutyRgnOnly": True,
            "includeSubsiCnstty": True,
        }
        p = build_search_params(conditions, "202611020000", "202611031229")
        assert p.inqryDiv == "1"  # 알림은 항상 '공고게시일시' 기준
        assert p.inqryBgnDt == "202611020000"
        assert p.inqryEndDt == "202611031229"
        assert p.prtcptLmtRgnNm == "서울특별시,경기도"
        assert p.cnstrtsiteRgnNm == "강남"
        assert p.indstrytyNm == "토목공사업,건축공사업"
        assert p.presmptPrceBgn == "1000000"
        assert p.presmptPrceEnd == "500000000"
        assert p.bidClseExcpYn == "Y"
        assert p.useLocationFilter is True
        assert p.incntvRgnOnly is True
        assert p.jntcontrctDutyRgnOnly is True
        assert p.includeSubsiCnstty is True
        assert p.numOfRows == 100 and p.pageNo == 1
        assert p.orderBy == "rgstDt" and p.orderDir == "desc"

    def test_empty_conditions_gives_plain_window(self):
        p = build_search_params({}, "a", "b")
        assert p.prtcptLmtRgnNm is None
        assert p.indstrytyNm is None
        assert not p.useLocationFilter
        assert not p.incntvRgnOnly

    def test_ignores_unknown_keys_and_cannot_override_window_or_paging(self):
        p = build_search_params(
            {
                "prtcptLmtRgnCd": "11",
                "inqryBgnDt": "19700101",
                "numOfRows": 99999,
                "pageNo": 50,
                "evil": 1,
            },
            "202611020000",
            "202611031229",
        )
        assert p.inqryBgnDt == "202611020000"
        assert p.numOfRows == 100 and p.pageNo == 1

    @pytest.mark.parametrize("bad", ["yes", 1, "true", [True], {}])
    def test_non_bool_flags_are_dropped(self, bad):
        p = build_search_params(
            {"useLocationFilter": bad, "incntvRgnOnly": bad,
             "jntcontrctDutyRgnOnly": bad, "includeSubsiCnstty": bad},
            "a", "b",
        )
        assert not p.useLocationFilter
        assert not p.incntvRgnOnly
        assert not p.jntcontrctDutyRgnOnly
        assert not p.includeSubsiCnstty

    def test_invalid_types_for_lists_and_prices_are_dropped(self):
        p = build_search_params(
            {"regions": 5, "industries": [1, None, ""], "priceStart": {"a": 1},
             "priceEnd": "abc", "excludeClosed": "maybe"},
            "a", "b",
        )
        assert p.prtcptLmtRgnNm is None
        assert p.indstrytyNm is None
        assert p.presmptPrceBgn is None
        assert p.presmptPrceEnd is None
        assert p.bidClseExcpYn is None

    def test_accepts_string_lists_and_numeric_prices(self):
        p = build_search_params(
            {"regions": "서울특별시, 경기도", "industries": "토목공사업",
             "priceStart": 1000, "excludeClosed": True},
            "a", "b",
        )
        assert p.prtcptLmtRgnNm == "서울특별시,경기도"
        assert p.indstrytyNm == "토목공사업"
        assert p.presmptPrceBgn == "1000"
        assert p.bidClseExcpYn == "Y"

    def test_non_dict_conditions(self):
        assert build_search_params(None, "a", "b").inqryBgnDt == "a"
        assert build_search_params(["x"], "a", "b").inqryEndDt == "b"


# ---------------------------------------------------------------------------
# 빈도 게이팅
# ---------------------------------------------------------------------------

class TestStrListCaps:
    def test_caps_item_count(self):
        from app.services.scheduler import MAX_LIST_ITEMS

        got = _str_list([f"r{i}" for i in range(MAX_LIST_ITEMS + 30)])
        assert len(got.split(",")) == MAX_LIST_ITEMS

    def test_caps_item_count_for_comma_string(self):
        from app.services.scheduler import MAX_LIST_ITEMS

        got = _str_list(",".join(f"r{i}" for i in range(500)))
        assert len(got.split(",")) == MAX_LIST_ITEMS

    def test_truncates_long_items(self):
        from app.services.scheduler import MAX_ITEM_LENGTH

        got = _str_list(["가" * 5000])
        assert len(got) == MAX_ITEM_LENGTH

    def test_normal_values_unchanged(self):
        assert _str_list(["서울특별시", " 경기도 "]) == "서울특별시,경기도"


class TestShouldNotify:
    def test_never_notified_is_due(self, sched):
        assert sched._should_notify(make_pref(), "daily", NOW) is True

    @pytest.mark.parametrize(
        "freq,delta,expected",
        [
            ("realtime", timedelta(minutes=59), False),
            ("realtime", timedelta(hours=1), True),
            ("daily", timedelta(hours=23), False),
            ("daily", timedelta(days=1), True),
            ("weekly", timedelta(days=6), False),
            ("weekly", timedelta(weeks=1), True),
            ("bogus", timedelta(days=30), False),
        ],
    )
    def test_frequency_boundaries_with_aware_datetimes(self, sched, freq, delta, expected):
        pref = make_pref(last=(NOW - delta).astimezone(timezone.utc))
        assert sched._should_notify(pref, freq, NOW) is expected

    def test_naive_last_notification_is_treated_as_utc(self, sched):
        naive = (NOW - timedelta(days=2)).astimezone(timezone.utc).replace(tzinfo=None)
        assert sched._should_notify(make_pref(last=naive), "daily", NOW) is True

    def test_default_now_is_timezone_aware(self, sched):
        pref = make_pref(last=datetime.now(timezone.utc) - timedelta(days=2))
        assert sched._should_notify(pref, "daily") is True  # TypeError 없이 동작


# ---------------------------------------------------------------------------
# notify_user
# ---------------------------------------------------------------------------

class TestNotifyUser:
    @pytest.mark.asyncio
    async def test_queries_db_not_external_api(self, sched, db, mocks):
        user = make_user()
        await sched.notify_user(db, user, make_pref({"industries": ["토목공사업"]}), NOW)
        mocks.bds.search_from_db.assert_awaited_once()
        args, kwargs = mocks.bds.search_from_db.call_args
        assert args[0] is db
        params = args[1]
        assert params.indstrytyNm == "토목공사업"
        assert (kwargs.get("user_id") or args[2]) == user.user_id

    @pytest.mark.asyncio
    async def test_window_uses_last_notification_in_kst(self, sched, db, mocks):
        last = datetime(2026, 11, 2, 3, 10, 0, tzinfo=timezone.utc)  # 12:10 KST
        await sched.notify_user(db, make_user(), make_pref(COND, last=last), NOW)
        params = mocks.bds.search_from_db.call_args.args[1]
        # rgst_dt 하한 = 직전 알림 - 1일 (늦게 동기화된 공고 커버)
        assert params.inqryBgnDt == "202611011210"
        assert params.inqryEndDt == "202611031230"
        # 중복 방지는 삽입 시각 기준
        kwargs = mocks.bds.search_from_db.call_args.kwargs
        assert kwargs["created_after"] == last
        assert kwargs["order_by_created_at"] is True

    @pytest.mark.parametrize(
        "freq,start",
        [("realtime", "202611031130"), ("daily", "202611021230"), ("weekly", "202610271230")],
    )
    @pytest.mark.asyncio
    async def test_fallback_window_by_frequency(self, sched, db, mocks, freq, start):
        await sched.notify_user(db, make_user(), make_pref(COND, frequency=freq), NOW)
        params = mocks.bds.search_from_db.call_args.args[1]
        assert params.inqryBgnDt == start

    @pytest.mark.asyncio
    async def test_stale_last_notification_window_is_capped_to_7_days(self, sched, db, mocks):
        pref = make_pref(COND, frequency="realtime", last=NOW - timedelta(days=90))
        await sched.notify_user(db, make_user(), pref, NOW)
        assert mocks.bds.search_from_db.call_args.args[1].inqryBgnDt == "202610271230"

    @pytest.mark.asyncio
    async def test_sends_email_then_updates_and_commits(self, sched, db, mocks):
        pref = make_pref(COND, last=NOW - timedelta(days=2))
        user = make_user("kim")
        order = []
        mocks.email.send_bid_notification.side_effect = lambda **kw: order.append("send") or True
        db.commit.side_effect = lambda: order.append("commit")
        sent = await sched.notify_user(db, user, pref, NOW)
        assert sent is True
        kw = mocks.email.send_bid_notification.call_args.kwargs
        assert kw["to_email"] == user.email and kw["username"] == "kim"
        assert len(kw["bid_notices"]) == 1
        # 발송한 공고의 마지막 삽입 시각 (now 가 아님)
        assert pref.last_notification_at == CREATED
        assert pref.last_notification_at.tzinfo is not None
        assert order == ["send", "commit"]

    @pytest.mark.asyncio
    async def test_first_run_has_no_created_after(self, sched, db, mocks):
        await sched.notify_user(db, make_user(), make_pref(COND), NOW)
        assert mocks.bds.search_from_db.call_args.kwargs["created_after"] is None

    @pytest.mark.asyncio
    async def test_naive_last_notification_is_treated_as_utc_for_created_after(
        self, sched, db, mocks
    ):
        naive = datetime(2026, 11, 1, 0, 0, 0)
        await sched.notify_user(db, make_user(), make_pref(COND, last=naive), NOW)
        got = mocks.bds.search_from_db.call_args.kwargs["created_after"]
        assert got == naive.replace(tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_late_synced_bid_is_found_on_next_run(self, sched, db, mocks):
        """rgst_dt 가 직전 알림보다 오래됐어도 created_after 로 걸러내지 않는다.

        윈도우 하한은 last-1일 이므로 하루 이내 늦게 들어온 공고는 조회 대상이다.
        """
        last = NOW - timedelta(days=2)
        await sched.notify_user(db, make_user(), make_pref(COND, last=last), NOW)
        params = mocks.bds.search_from_db.call_args.args[1]
        assert params.inqryBgnDt < last.strftime("%Y%m%d%H%M")

    @pytest.mark.asyncio
    async def test_overflow_advances_cursor_to_last_sent_item_not_now(
        self, sched, db, mocks
    ):
        items = [make_bid(f"R{i}") for i in range(100)]
        mocks.bds.search_from_db.return_value = BidApiResponse(
            items=items, totalCount=250, numOfRows=100, pageNo=1
        )
        pref = make_pref(COND, last=NOW - timedelta(days=2))
        await sched.notify_user(db, make_user(), pref, NOW)
        keys = mocks.bds.max_created_at.call_args.args[1]
        assert len(keys) == 100
        assert pref.last_notification_at == CREATED
        assert pref.last_notification_at < NOW

    @pytest.mark.asyncio
    async def test_cursor_falls_back_to_current_minute_when_created_at_unknown(
        self, sched, db, mocks
    ):
        mocks.bds.max_created_at.return_value = None
        pref = make_pref(COND)
        await sched.notify_user(db, make_user(), pref, NOW)
        assert pref.last_notification_at == datetime(2026, 11, 3, 12, 30, tzinfo=KST)

    @pytest.mark.asyncio
    async def test_not_due_skips_everything(self, sched, db, mocks):
        pref = make_pref(COND, last=NOW - timedelta(hours=2))
        assert await sched.notify_user(db, make_user(), pref, NOW) is False
        mocks.bds.search_from_db.assert_not_awaited()
        mocks.email.send_bid_notification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_results_sends_nothing_and_does_not_touch_state(self, sched, db, mocks):
        mocks.bds.search_from_db.return_value = response([])
        pref = make_pref(COND)
        assert await sched.notify_user(db, make_user(), pref, NOW) is False
        mocks.email.send_bid_notification.assert_not_awaited()
        db.commit.assert_not_awaited()
        assert pref.last_notification_at is None

    @pytest.mark.asyncio
    async def test_empty_conditions_skipped(self, sched, db, mocks):
        # 저장된 조건이 없으면(빈 dict) 조회하지 않는다
        assert await sched.notify_user(db, make_user(), make_pref({}), NOW) is False
        mocks.bds.search_from_db.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_failure_keeps_state_and_raises_nothing_committed(self, sched, db, mocks):
        mocks.email.send_bid_notification.return_value = False
        pref = make_pref({"industries": ["x"]}, last=NOW - timedelta(days=2))
        before = pref.last_notification_at
        assert await sched.notify_user(db, make_user(), pref, NOW) is False
        assert pref.last_notification_at == before
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_exception_propagates_without_commit(self, sched, db, mocks):
        mocks.email.send_bid_notification.side_effect = RuntimeError("smtp")
        pref = make_pref({"industries": ["x"]})
        with pytest.raises(RuntimeError):
            await sched.notify_user(db, make_user(), pref, NOW)
        assert pref.last_notification_at is None
        db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# check_and_notify
# ---------------------------------------------------------------------------

class FakeSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


class TestCheckAndNotify:
    @pytest.mark.asyncio
    async def test_one_user_failure_does_not_stop_others(self, sched, db):
        u1, u2 = make_user("a"), make_user("b")
        p1, p2 = make_pref({"industries": ["x"]}), make_pref({"industries": ["x"]})
        result = MagicMock()
        result.all.return_value = [(u1, p1), (u2, p2)]
        db.execute = AsyncMock(return_value=result)
        calls = []

        async def fake_notify(session, user, pref, now=None):
            calls.append(user.username)
            if user is u1:
                raise RuntimeError("boom")
            return True

        sched.notify_user = fake_notify
        with patch("app.services.scheduler.AsyncSessionLocal", FakeSessionFactory(db)):
            await sched.check_and_notify()
        assert calls == ["a", "b"]
        db.rollback.assert_awaited()  # 실패한 사용자 변경분 폐기

    @pytest.mark.asyncio
    async def test_no_users(self, sched, db):
        result = MagicMock()
        result.all.return_value = []
        db.execute = AsyncMock(return_value=result)
        with patch("app.services.scheduler.AsyncSessionLocal", FakeSessionFactory(db)):
            await sched.check_and_notify()


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, sched):
        sched.is_running = True
        await sched.stop()
        assert sched.is_running is False
