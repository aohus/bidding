"""external_bid_sync_scheduler 테스트.

고정하는 핵심 동작:
  1. 수집 실패한 윈도우는 **마킹하지 않는다** (마킹하면 영구 누락).
  2. 월 단위 소스(수자원)는 월별 윈도우를 쓴다 — 일별로 돌리면 같은 달을
     매일 재조회한다.
  3. 최근 N일은 항상 재수집, 그 이전은 미동기화 윈도우만 백필.
  4. 모든 키 소진 시 사이클을 즉시 중단한다.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.external_bid_sync_scheduler import (
    KST,
    ExternalBidSyncScheduler,
)
from app.services.external_sources.base import ExternalRateLimitError
from app.services.external_sources.mapping import (
    NoticeRecord,
    ResultRecord,
    SourceFetch,
)


def fake_source(source="kdhc", granularity="day", fetch=None):
    return SimpleNamespace(
        source=source,
        name=source,
        granularity=granularity,
        fetch=fetch or AsyncMock(return_value=SourceFetch(api_calls=1)),
    )


class FakeSession:
    """AsyncSessionLocal() 컨텍스트매니저 대역."""

    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


def patch_session():
    return patch(
        "app.services.external_bid_sync_scheduler.AsyncSessionLocal",
        new=lambda: FakeSession(),
    )


def patch_service(entry=None):
    svc = MagicMock()
    svc.get_sync_entry = AsyncMock(return_value=entry)
    svc.save_notices = AsyncMock(return_value=0)
    svc.save_results = AsyncMock(return_value=0)
    svc.mark_window_synced = AsyncMock()
    return patch(
        "app.services.external_bid_sync_scheduler.external_bid_service", svc
    ), svc


@pytest.fixture
def scheduler():
    sched = ExternalBidSyncScheduler()
    sched.RECENT_DAYS = 2
    sched.BACKFILL_DAYS = 5
    sched.MAX_BACKFILL_WINDOWS = 1
    sched.SOURCE_PAUSE_SECONDS = 0
    sched.WINDOW_PAUSE_SECONDS = 0
    return sched


# ---------------------------------------------------------------------------
# 윈도우 계획
# ---------------------------------------------------------------------------

class TestPlanWindows:
    def test_day_source_recent_windows_always_resync(self, scheduler):
        windows = scheduler._plan_windows(fake_source(granularity="day"))

        always = [w for w in windows if w[2]]
        assert len(always) == scheduler.RECENT_DAYS

    def test_day_source_backfill_windows_are_conditional(self, scheduler):
        windows = scheduler._plan_windows(fake_source(granularity="day"))

        conditional = [w for w in windows if not w[2]]
        assert len(conditional) == scheduler.MAX_BACKFILL_WINDOWS

    def test_day_windows_are_full_day_spans(self, scheduler):
        windows = scheduler._plan_windows(fake_source(granularity="day"))

        for start, end, _ in windows:
            assert start.endswith("0000")
            assert end.endswith("2359")
            assert start[:8] == end[:8]

    def test_day_windows_are_newest_first(self, scheduler):
        windows = scheduler._plan_windows(fake_source(granularity="day"))
        starts = [w[0] for w in windows]

        assert starts == sorted(starts, reverse=True)

    def test_today_is_first_window(self, scheduler):
        windows = scheduler._plan_windows(fake_source(granularity="day"))
        today = datetime.now(KST).strftime("%Y%m%d")

        assert windows[0][0] == f"{today}0000"

    def test_month_source_uses_month_windows(self, scheduler):
        windows = scheduler._plan_windows(
            fake_source(source="kwater", granularity="month")
        )

        for start, end, _ in windows:
            assert start.endswith("010000")
            assert end.endswith("2359")

    def test_month_source_current_month_always_resync(self, scheduler):
        windows = scheduler._plan_windows(
            fake_source(source="kwater", granularity="month")
        )

        assert windows[0][2] is True
        assert all(not w[2] for w in windows[1:])

    def test_month_source_covers_backfill_span(self, scheduler):
        scheduler.BACKFILL_DAYS = 70
        windows = scheduler._plan_windows(
            fake_source(source="kwater", granularity="month")
        )

        # 70일이면 최소 3개월(당월 + 2개월)이 걸친다.
        assert len(windows) >= 3

    def test_month_list_has_no_duplicates(self, scheduler):
        windows = scheduler._plan_windows(
            fake_source(source="kwater", granularity="month")
        )
        starts = [w[0] for w in windows]

        assert len(starts) == len(set(starts))


# ---------------------------------------------------------------------------
# 윈도우 동기화
# ---------------------------------------------------------------------------

class TestSyncWindow:
    @pytest.mark.asyncio
    async def test_saves_and_marks_on_success(self, scheduler):
        fetch = AsyncMock(
            return_value=SourceFetch(
                notices=(
                    NoticeRecord(source="kdhc", notice_no="N1", notice_ord="00"),
                ),
                results=(
                    ResultRecord(source="kdhc", notice_no="N1", notice_ord="00"),
                ),
                api_calls=2,
            )
        )
        ctx, svc = patch_service()
        with patch_session(), ctx:
            calls = await scheduler._sync_window(
                fake_source(fetch=fetch), "202610120000", "202610122359"
            )

        assert calls == 2
        svc.save_notices.assert_awaited_once()
        svc.save_results.assert_awaited_once()
        svc.mark_window_synced.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_mark_when_fetch_fails(self, scheduler):
        """마킹하면 그 구간이 영구 누락된다."""
        fetch = AsyncMock(side_effect=RuntimeError("boom"))
        ctx, svc = patch_service()
        with patch_session(), ctx:
            await scheduler._sync_window(
                fake_source(fetch=fetch), "202610120000", "202610122359"
            )

        svc.mark_window_synced.assert_not_awaited()
        assert scheduler._failed_windows

    @pytest.mark.asyncio
    async def test_does_not_mark_when_persist_fails(self, scheduler):
        fetch = AsyncMock(return_value=SourceFetch(api_calls=1))
        ctx, svc = patch_service()
        svc.save_notices.side_effect = RuntimeError("db down")
        with patch_session(), ctx:
            await scheduler._sync_window(
                fake_source(fetch=fetch), "202610120000", "202610122359"
            )

        svc.mark_window_synced.assert_not_awaited()
        assert any("저장 실패" in w for w in scheduler._failed_windows)

    @pytest.mark.asyncio
    async def test_rate_limit_propagates(self, scheduler):
        fetch = AsyncMock(side_effect=ExternalRateLimitError("quota", code="22"))
        ctx, _ = patch_service()
        with patch_session(), ctx:
            with pytest.raises(ExternalRateLimitError):
                await scheduler._sync_window(
                    fake_source(fetch=fetch), "202610120000", "202610122359"
                )

    @pytest.mark.asyncio
    async def test_failed_window_label_includes_source_and_range(
        self, scheduler
    ):
        fetch = AsyncMock(side_effect=RuntimeError("boom"))
        ctx, _ = patch_service()
        with patch_session(), ctx:
            await scheduler._sync_window(
                fake_source(source="lh", fetch=fetch),
                "202610120000",
                "202610122359",
            )

        label = scheduler._failed_windows[0]
        assert "lh" in label
        assert "202610120000~202610122359" in label


# ---------------------------------------------------------------------------
# 소스 순회 / 사이클
# ---------------------------------------------------------------------------

class TestSyncSource:
    @pytest.mark.asyncio
    async def test_skips_already_synced_backfill_window(self, scheduler):
        fetch = AsyncMock(return_value=SourceFetch(api_calls=1))
        ctx, svc = patch_service(entry=MagicMock())
        with patch_session(), ctx:
            await scheduler._sync_source(fake_source(fetch=fetch), 0)

        # 최근 RECENT_DAYS 만 수집하고 백필 윈도우는 skip 되어야 한다.
        assert fetch.await_count == scheduler.RECENT_DAYS

    @pytest.mark.asyncio
    async def test_fetches_backfill_window_when_not_synced(self, scheduler):
        fetch = AsyncMock(return_value=SourceFetch(api_calls=1))
        ctx, _ = patch_service(entry=None)
        with patch_session(), ctx:
            await scheduler._sync_source(fake_source(fetch=fetch), 0)

        expected = scheduler.RECENT_DAYS + scheduler.MAX_BACKFILL_WINDOWS
        assert fetch.await_count == expected

    @pytest.mark.asyncio
    async def test_stops_at_api_call_budget(self, scheduler):
        scheduler.MAX_API_CALLS_PER_RUN = 1
        fetch = AsyncMock(return_value=SourceFetch(api_calls=1))
        ctx, _ = patch_service(entry=None)
        with patch_session(), ctx:
            used = await scheduler._sync_source(fake_source(fetch=fetch), 0)

        assert used == 1
        assert fetch.await_count == 1


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_iterates_all_registered_sources(self, scheduler):
        calls = []

        def make(source_id):
            async def _fetch(start, end):
                calls.append(source_id)
                return SourceFetch(api_calls=1)

            return fake_source(source=source_id, fetch=_fetch)

        sources = {sid: make(sid) for sid in ("a", "b")}
        ctx, _ = patch_service(entry=MagicMock())
        with patch_session(), ctx, patch(
            "app.services.external_bid_sync_scheduler.SOURCES", sources
        ):
            await scheduler.run_cycle()

        assert set(calls) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_aborts_cycle_when_all_keys_exhausted(self, scheduler):
        touched = []

        def make(source_id, fail):
            async def _fetch(start, end):
                touched.append(source_id)
                if fail:
                    raise ExternalRateLimitError("quota", code="22")
                return SourceFetch(api_calls=1)

            return fake_source(source=source_id, fetch=_fetch)

        sources = {"a": make("a", True), "b": make("b", False)}
        ctx, _ = patch_service(entry=MagicMock())
        with patch_session(), ctx, patch(
            "app.services.external_bid_sync_scheduler.SOURCES", sources
        ), patch.object(
            scheduler, "_send_failure_alert", new=AsyncMock()
        ):
            await scheduler.run_cycle()

        assert touched == ["a"]

    @pytest.mark.asyncio
    async def test_sends_alert_when_failures_occur(self, scheduler):
        async def _fetch(start, end):
            raise RuntimeError("boom")

        sources = {"a": fake_source(source="a", fetch=_fetch)}
        ctx, _ = patch_service(entry=MagicMock())
        alert = AsyncMock()
        with patch_session(), ctx, patch(
            "app.services.external_bid_sync_scheduler.SOURCES", sources
        ), patch.object(scheduler, "_send_failure_alert", new=alert):
            await scheduler.run_cycle()

        alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_alert_when_all_succeed(self, scheduler):
        sources = {"a": fake_source(source="a")}
        ctx, _ = patch_service(entry=MagicMock())
        alert = AsyncMock()
        with patch_session(), ctx, patch(
            "app.services.external_bid_sync_scheduler.SOURCES", sources
        ), patch.object(scheduler, "_send_failure_alert", new=alert):
            await scheduler.run_cycle()

        alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_one_source_failure_does_not_stop_others(self, scheduler):
        touched = []

        def make(source_id, fail):
            async def _fetch(start, end):
                touched.append(source_id)
                if fail:
                    raise RuntimeError("boom")
                return SourceFetch(api_calls=1)

            return fake_source(source=source_id, fetch=_fetch)

        sources = {"a": make("a", True), "b": make("b", False)}
        ctx, _ = patch_service(entry=MagicMock())
        with patch_session(), ctx, patch(
            "app.services.external_bid_sync_scheduler.SOURCES", sources
        ), patch.object(scheduler, "_send_failure_alert", new=AsyncMock()):
            await scheduler.run_cycle()

        assert set(touched) == {"a", "b"}


class TestAlertThrottle:
    @pytest.mark.asyncio
    async def test_throttles_within_an_hour(self, scheduler):
        scheduler._failed_windows = ["x"]
        scheduler._last_alert_at = datetime.now(KST) - timedelta(minutes=5)
        email = MagicMock()
        email.send_email = AsyncMock(return_value=True)

        with patch("app.services.email_service.email_service", email):
            await scheduler._send_failure_alert()

        email.send_email.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sends_after_throttle_window(self, scheduler):
        scheduler._failed_windows = ["x"]
        scheduler._last_alert_at = datetime.now(KST) - timedelta(hours=2)
        email = MagicMock()
        email.send_email = AsyncMock(return_value=True)

        with patch("app.services.email_service.email_service", email), patch(
            "app.core.config.settings.ALERT_EMAIL", "a@b.com"
        ):
            await scheduler._send_failure_alert()

        email.send_email.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_email_configured_is_not_an_error(self, scheduler):
        scheduler._failed_windows = ["x"]
        email = MagicMock()
        email.send_email = AsyncMock(return_value=True)

        with patch("app.services.email_service.email_service", email), patch(
            "app.core.config.settings.ALERT_EMAIL", ""
        ), patch("app.core.config.settings.FROM_EMAIL", ""):
            await scheduler._send_failure_alert()

        email.send_email.assert_not_awaited()


class TestIndependenceFromNarajangter:
    def test_uses_its_own_lock(self, scheduler):
        from app.services.bid_sync_scheduler import bid_sync_scheduler

        assert scheduler._sync_lock is not bid_sync_scheduler._sync_lock

    def test_default_flag_is_off(self):
        """배포 직후 자동 수집이 시작되면 안 된다 (마이그레이션 선행 필요)."""
        from app.core.config import Settings

        field = Settings.model_fields["ENABLE_EXTERNAL_BID_SYNC"]
        assert field.default is False
