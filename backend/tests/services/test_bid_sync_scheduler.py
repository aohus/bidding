"""동기화 스케줄러 회귀 테스트.

여기서 고정하는 핵심 동작:
  1. 일별 백필은 '일별' 윈도우 기록으로만 skip 판단해야 한다.
     (자정 시간별 윈도우와 sync_timestamp 가 같아 혼동되면 영구 skip 된다)
  2. 부분 실패한 윈도우는 완료 마킹하면 안 된다.
  3. API 호출 수는 페이지 단위 실호출로 집계해야 한다.
  4. 한도 소진(RateLimitError)은 사이클을 중단시켜야 한다.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.bid_sync_scheduler import BidDataSyncScheduler
from app.services.narajangter import NaraJangterApiError, RateLimitError


class FakeSessionFactory:
    """`async with AsyncSessionLocal() as db:` 를 흉내냅니다."""

    def __init__(self):
        self.session = MagicMock()

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc_info):
        return False


@pytest.fixture
def scheduler():
    return BidDataSyncScheduler()


@pytest.fixture
def fake_sessions():
    return FakeSessionFactory()


# ---------------------------------------------------------------------------
# 일별 백필 skip 판정
# ---------------------------------------------------------------------------

class TestBackfillSkipDecision:
    @pytest.mark.asyncio
    async def test_backfill_asks_for_daily_window_not_bare_timestamp(
        self, scheduler, fake_sessions
    ):
        """백필은 get_daily_sync_entry 로 물어야 한다.

        시작 시각(YYYYMMDD0000)만으로 조회하면 자정 시간별 윈도우가 잡혀
        그 날 백필이 영구히 skip 된다 — 이 버그의 직접 원인.
        """
        daily = AsyncMock(return_value=None)

        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch(
            "app.services.bid_data_service.bid_data_service.get_daily_sync_entry",
            daily,
        ), patch.object(
            scheduler, "_sync_window_internal", AsyncMock(return_value=4)
        ), patch(
            "asyncio.sleep", AsyncMock()
        ):
            await scheduler._backfill_past_days(0)

        assert daily.await_count > 0
        for call in daily.await_args_list:
            date_str = call.args[1]
            assert len(date_str) == 8, "YYYYMMDD 형식이어야 함"

    @pytest.mark.asyncio
    async def test_backfill_runs_when_no_daily_entry(
        self, scheduler, fake_sessions
    ):
        sync_window = AsyncMock(return_value=4)

        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch(
            "app.services.bid_data_service.bid_data_service.get_daily_sync_entry",
            AsyncMock(return_value=None),
        ), patch.object(
            scheduler, "_sync_window_internal", sync_window
        ), patch(
            "asyncio.sleep", AsyncMock()
        ):
            await scheduler._backfill_past_days(0)

        assert sync_window.await_count == scheduler.MAX_BACKFILL_PER_RUN

    @pytest.mark.asyncio
    async def test_backfill_skips_when_daily_entry_exists(
        self, scheduler, fake_sessions
    ):
        sync_window = AsyncMock(return_value=4)

        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch(
            "app.services.bid_data_service.bid_data_service.get_daily_sync_entry",
            AsyncMock(return_value=MagicMock(window_end="202608042359")),
        ), patch.object(
            scheduler, "_sync_window_internal", sync_window
        ), patch(
            "asyncio.sleep", AsyncMock()
        ):
            await scheduler._backfill_past_days(0)

        assert sync_window.await_count == 0

    @pytest.mark.asyncio
    async def test_manual_sync_force_ignores_existing_entry(
        self, scheduler, fake_sessions
    ):
        """force=True 면 완료 기록이 있어도 재동기화해야 복구가 가능하다."""
        sync_window = AsyncMock(return_value=4)
        daily = AsyncMock(return_value=MagicMock(window_end="202608042359"))

        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch(
            "app.services.bid_data_service.bid_data_service.get_daily_sync_entry",
            daily,
        ), patch.object(
            scheduler, "_sync_window_internal", sync_window
        ), patch(
            "asyncio.sleep", AsyncMock()
        ):
            await scheduler._sync_days(datetime.now(timezone.utc), days=2, force=True)

        assert sync_window.await_count == 3  # day_offset 2,1,0
        assert daily.await_count == 0

    @pytest.mark.asyncio
    async def test_manual_sync_without_force_skips(self, scheduler, fake_sessions):
        sync_window = AsyncMock(return_value=4)

        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch(
            "app.services.bid_data_service.bid_data_service.get_daily_sync_entry",
            AsyncMock(return_value=MagicMock(window_end="202608042359")),
        ), patch.object(
            scheduler, "_sync_window_internal", sync_window
        ), patch(
            "asyncio.sleep", AsyncMock()
        ):
            await scheduler._sync_days(datetime.now(timezone.utc), days=2, force=False)

        assert sync_window.await_count == 0

    @pytest.mark.asyncio
    async def test_hourly_sync_uses_full_window_key(self, scheduler, fake_sessions):
        """시간별 조회는 (시작, 끝) 쌍으로 물어야 자정 윈도우와 안 겹친다."""
        get_entry = AsyncMock(return_value=None)

        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch(
            "app.services.bid_data_service.bid_data_service.get_sync_entry",
            get_entry,
        ), patch.object(
            scheduler, "_sync_window_internal", AsyncMock(return_value=4)
        ), patch(
            "asyncio.sleep", AsyncMock()
        ):
            await scheduler._sync_recent_hours(0)

        assert get_entry.await_count == scheduler.RECENT_HOURS
        for call in get_entry.await_args_list:
            start, end = call.args[1], call.args[2]
            assert start.endswith("00")
            assert end.endswith("59")
            assert start[:10] == end[:10]


# ---------------------------------------------------------------------------
# 윈도우 완료 마킹 조건
# ---------------------------------------------------------------------------

class TestWindowMarking:
    async def _run_window(self, scheduler, fake_sessions, results, mark):
        with patch(
            "app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions
        ), patch.object(
            scheduler, "_fetch_notices", AsyncMock(side_effect=results["notices"])
        ), patch.object(
            scheduler, "_fetch_regions", AsyncMock(return_value=results["regions"])
        ), patch.object(
            scheduler,
            "_fetch_license_limits",
            AsyncMock(return_value=results["licenses"]),
        ), patch.object(
            scheduler,
            "_fetch_incntv_rgns",
            AsyncMock(return_value=results.get("incntv", (0, True, 0))),
        ), patch.object(
            scheduler,
            "_fetch_jntcontrct_duty_rgns",
            AsyncMock(return_value=results.get("jntcontrct", (0, True, 0))),
        ), patch.object(
            scheduler,
            "_fetch_subsi_cnsttys",
            AsyncMock(return_value=results.get("subsi", (0, True, 0))),
        ), patch(
            "app.services.bid_data_service.bid_data_service.mark_window_synced",
            mark,
        ):
            return await scheduler._sync_window_internal(
                "202608040000", "202608042359"
            )

    @pytest.mark.asyncio
    async def test_marks_when_all_succeed(self, scheduler, fake_sessions):
        mark = AsyncMock()
        calls = await self._run_window(
            scheduler,
            fake_sessions,
            {
                "notices": [(10, True, 1), (5, True, 1)],
                "regions": (20, True, 1),
                "licenses": (30, True, 1),
            },
            mark,
        )

        assert mark.await_count == 1
        assert calls == 4
        args = mark.await_args.args
        assert args[1] == "202608040000"
        assert args[2] == "202608042359"

    @pytest.mark.asyncio
    async def test_passes_sub_dataset_counts_and_api_calls(
        self, scheduler, fake_sessions
    ):
        mark = AsyncMock()
        calls = await self._run_window(
            scheduler,
            fake_sessions,
            {
                "notices": [(10, True, 1), (5, True, 1)],
                "regions": (20, True, 1),
                "licenses": (30, True, 1),
                "incntv": (4, True, 1),
                "jntcontrct": (5, True, 1),
                "subsi": (6, True, 2),
            },
            mark,
        )

        assert calls == 4 + 1 + 1 + 2
        assert mark.await_args.args[3:6] == (15, 20, 30)
        assert mark.await_args.kwargs == {
            "total_incntv_rgns": 4,
            "total_jntcontrct_duty_rgns": 5,
            "total_subsi_cnsttys": 6,
            "sub_datasets_synced": True,
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failing", ["incntv", "jntcontrct", "subsi"])
    async def test_sub_dataset_failure_does_not_block_window_mark(
        self, scheduler, fake_sessions, failing
    ):
        """신규 오퍼레이션 하나(예: 403)가 공고 윈도우 마킹 전체를 막으면 안 된다."""
        mark = AsyncMock()
        results = {
            "notices": [(10, True, 1), (5, True, 1)],
            "regions": (20, True, 1),
            "licenses": (30, True, 1),
            failing: (0, False, 1),
        }
        await self._run_window(scheduler, fake_sessions, results, mark)

        assert mark.await_count == 1
        assert mark.await_args.kwargs["sub_datasets_synced"] is False
        assert scheduler._failed_windows == []

    @pytest.mark.asyncio
    async def test_does_not_mark_when_license_fetch_fails(
        self, scheduler, fake_sessions
    ):
        """면허제한만 실패해도 마킹하면 안 된다.

        마킹되면 그 구간 공고가 업종명 필터 검색에서 영구히 빠진다.
        """
        mark = AsyncMock()
        await self._run_window(
            scheduler,
            fake_sessions,
            {
                "notices": [(10, True, 1), (5, True, 1)],
                "regions": (20, True, 1),
                "licenses": (0, False, 1),
            },
            mark,
        )

        assert mark.await_count == 0
        assert scheduler._failed_windows == ["202608040000~202608042359"]

    @pytest.mark.asyncio
    async def test_does_not_mark_when_regions_fetch_fails(
        self, scheduler, fake_sessions
    ):
        mark = AsyncMock()
        await self._run_window(
            scheduler,
            fake_sessions,
            {
                "notices": [(10, True, 1), (5, True, 1)],
                "regions": (0, False, 1),
                "licenses": (30, True, 1),
            },
            mark,
        )
        assert mark.await_count == 0

    @pytest.mark.asyncio
    async def test_counts_actual_pages_not_fixed_four(
        self, scheduler, fake_sessions
    ):
        """호출 수는 페이지 단위 실호출이어야 한다.

        고정 4로 세면 일별 윈도우(수십 페이지)에서 MAX_API_CALLS_PER_RUN
        가드가 무력화되어 429 를 유발한다.
        """
        mark = AsyncMock()
        calls = await self._run_window(
            scheduler,
            fake_sessions,
            {
                "notices": [(435, True, 5), (624, True, 7)],
                "regions": (1486, True, 2),
                "licenses": (1602, True, 2),
            },
            mark,
        )
        assert calls == 16


# ---------------------------------------------------------------------------
# _fetch_paged 공통 루프
# ---------------------------------------------------------------------------

class TestFetchPaged:
    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, scheduler):
        pages = [
            [object()] * 999,
            [object()] * 999,
            [object()] * 12,
        ]
        fetch = AsyncMock(side_effect=pages)
        save = AsyncMock()

        with patch("asyncio.sleep", AsyncMock()):
            total, success, calls = await scheduler._fetch_paged(
                "x", fetch, save, MagicMock(), "b", "e"
            )

        assert total == 999 + 999 + 12
        assert success is True
        assert calls == 3
        assert save.await_count == 3

    @pytest.mark.asyncio
    async def test_empty_first_page_is_success(self, scheduler):
        fetch = AsyncMock(return_value=[])
        total, success, calls = await scheduler._fetch_paged(
            "x", fetch, AsyncMock(), MagicMock(), "b", "e"
        )
        assert (total, success, calls) == (0, True, 1)

    @pytest.mark.asyncio
    async def test_api_error_marks_failure(self, scheduler):
        fetch = AsyncMock(side_effect=NaraJangterApiError("boom", code="01"))
        total, success, calls = await scheduler._fetch_paged(
            "x", fetch, AsyncMock(), MagicMock(), "b", "e"
        )
        assert success is False
        assert calls == 1

    @pytest.mark.asyncio
    async def test_error_on_later_page_keeps_partial_and_fails(self, scheduler):
        fetch = AsyncMock(
            side_effect=[[object()] * 999, NaraJangterApiError("boom", code="02")]
        )
        save = AsyncMock()

        with patch("asyncio.sleep", AsyncMock()):
            total, success, calls = await scheduler._fetch_paged(
                "x", fetch, save, MagicMock(), "b", "e"
            )

        assert total == 999
        assert success is False
        assert calls == 2

    @pytest.mark.asyncio
    async def test_rate_limit_propagates(self, scheduler):
        """한도 소진은 삼키지 않고 위로 올려 사이클을 끊어야 한다."""
        fetch = AsyncMock(side_effect=RateLimitError("exhausted", code="22"))
        with pytest.raises(RateLimitError):
            await scheduler._fetch_paged(
                "x", fetch, AsyncMock(), MagicMock(), "b", "e"
            )


# ---------------------------------------------------------------------------
# 한도 소진 시 사이클 중단
# ---------------------------------------------------------------------------

class TestRateLimitAbortsCycle:
    @pytest.mark.asyncio
    async def test_cycle_aborts_and_alerts(self, scheduler):
        alert = AsyncMock()

        with patch.object(
            scheduler,
            "_sync_recent_hours",
            AsyncMock(side_effect=RateLimitError("all keys exhausted", code="22")),
        ), patch.object(
            scheduler, "_backfill_past_days", AsyncMock()
        ) as backfill, patch.object(
            scheduler, "_sync_reserve_prices", AsyncMock()
        ) as reserve, patch.object(
            scheduler, "_send_failure_alert", alert
        ):
            await scheduler._run_sync_cycle()

        assert backfill.await_count == 0
        assert reserve.await_count == 0
        assert alert.await_count == 1
        assert "한도 소진" in scheduler._failed_windows[0]

    @pytest.mark.asyncio
    async def test_manual_sync_aborts_on_rate_limit(self, scheduler):
        alert = AsyncMock()

        with patch.object(
            scheduler,
            "_sync_days",
            AsyncMock(side_effect=RateLimitError("exhausted", code="22")),
        ), patch.object(scheduler, "_send_failure_alert", alert):
            await scheduler.sync_recent_data(days=3)

        assert alert.await_count == 1


class TestSubDatasetFetchWrappers:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,fetch_name,save_name",
        [
            ("_fetch_incntv_rgns", "get_incntv_rgn_by_date", "save_incntv_rgns"),
            (
                "_fetch_jntcontrct_duty_rgns",
                "get_jntcontrct_duty_rgn_by_date",
                "save_jntcontrct_duty_rgns",
            ),
            ("_fetch_subsi_cnsttys", "get_subsi_cnstty_by_date", "save_subsi_cnsttys"),
        ],
    )
    async def test_wrapper_pages_and_saves(
        self, scheduler, method, fetch_name, save_name
    ):
        fetch = AsyncMock(return_value=[object(), object()])
        save = AsyncMock()
        with patch(
            f"app.services.bid_sync_scheduler.narajangter_service.{fetch_name}",
            fetch,
        ), patch(
            f"app.services.bid_sync_scheduler.bid_data_service.{save_name}", save
        ):
            total, ok, calls = await getattr(scheduler, method)(
                "db", "202608040000", "202608042359"
            )

        assert (total, ok, calls) == (2, True, 1)
        fetch.assert_awaited_once_with("202608040000", "202608042359", 1)
        save.assert_awaited_once()



# ---------------------------------------------------------------------------
# 부속 데이터셋 재시도 단계
# ---------------------------------------------------------------------------

DAILY = ("202608040000", "202608042359")


class TestSubDatasetRetry:
    def _patch(self, scheduler, fake_sessions, windows, **fetch):
        mark = AsyncMock()
        stack = [
            patch("app.services.bid_sync_scheduler.AsyncSessionLocal", fake_sessions),
            patch(
                "app.services.bid_data_service.bid_data_service."
                "list_windows_pending_sub_datasets",
                AsyncMock(return_value=windows),
            ),
            patch(
                "app.services.bid_data_service.bid_data_service."
                "mark_sub_datasets_synced",
                mark,
            ),
            patch("app.services.bid_sync_scheduler.asyncio.sleep", AsyncMock()),
        ]
        for name, rv in (
            ("_fetch_incntv_rgns", fetch.get("incntv", (1, True, 1))),
            ("_fetch_jntcontrct_duty_rgns", fetch.get("jntcontrct", (2, True, 1))),
            ("_fetch_subsi_cnsttys", fetch.get("subsi", (3, True, 1))),
        ):
            if isinstance(rv, list):
                stack.append(patch.object(scheduler, name, AsyncMock(side_effect=rv)))
            else:
                stack.append(patch.object(scheduler, name, AsyncMock(return_value=rv)))
        return mark, stack

    async def _run(self, scheduler, fake_sessions, windows, api_calls=0, **fetch):
        from contextlib import ExitStack

        mark, stack = self._patch(scheduler, fake_sessions, windows, **fetch)
        with ExitStack() as es:
            for p in stack:
                es.enter_context(p)
            calls = await scheduler._retry_sub_datasets(api_calls)
        return calls, mark

    @pytest.mark.asyncio
    async def test_success_sets_flag_with_counts(self, scheduler, fake_sessions):
        calls, mark = await self._run(scheduler, fake_sessions, [DAILY])

        assert calls == 3
        assert mark.await_count == 1
        assert mark.await_args.args[1:3] == DAILY
        assert mark.await_args.args[3:] == (1, 2, 3)

    @pytest.mark.asyncio
    async def test_failure_stops_retry_step_for_this_run(
        self, scheduler, fake_sessions
    ):
        w2 = ("202608030000", "202608032359")
        calls, mark = await self._run(
            scheduler, fake_sessions, [DAILY, w2], subsi=(0, False, 1)
        )

        assert mark.await_count == 0
        assert calls == 3  # 두 번째 윈도우는 시도하지 않음
        assert scheduler._failed_windows == []

    @pytest.mark.asyncio
    async def test_respects_api_call_budget(self, scheduler, fake_sessions):
        calls, mark = await self._run(
            scheduler,
            fake_sessions,
            [DAILY],
            api_calls=BidDataSyncScheduler.MAX_API_CALLS_PER_RUN,
        )
        assert mark.await_count == 0
        assert calls == BidDataSyncScheduler.MAX_API_CALLS_PER_RUN

    @pytest.mark.asyncio
    async def test_stops_between_windows_when_budget_exhausted(
        self, scheduler, fake_sessions
    ):
        w2 = ("202608030000", "202608032359")
        calls, mark = await self._run(
            scheduler,
            fake_sessions,
            [DAILY, w2],
            api_calls=BidDataSyncScheduler.MAX_API_CALLS_PER_RUN - 3,
        )
        assert mark.await_count == 1
        assert calls == BidDataSyncScheduler.MAX_API_CALLS_PER_RUN

    @pytest.mark.asyncio
    async def test_rate_limit_propagates(self, scheduler, fake_sessions):
        with pytest.raises(RateLimitError):
            await self._run(
                scheduler,
                fake_sessions,
                [DAILY],
                incntv=[RateLimitError("x", code="22")],
            )

    @pytest.mark.asyncio
    async def test_cycle_runs_retry_step_after_backfill(self, scheduler):
        order = []

        def step(name, ret):
            async def run(_calls):
                order.append(name)
                return ret

            return run

        with patch.object(
            scheduler, "_sync_recent_hours", AsyncMock(side_effect=step("h", 1))
        ), patch.object(
            scheduler, "_backfill_past_days", AsyncMock(side_effect=step("b", 2))
        ), patch.object(
            scheduler, "_retry_sub_datasets", AsyncMock(side_effect=step("r", 3))
        ) as retry, patch.object(
            scheduler, "_sync_reserve_prices", AsyncMock()
        ) as reserve:
            await scheduler._run_sync_cycle()

        assert order == ["h", "b", "r"]
        retry.assert_awaited_once_with(2)
        reserve.assert_awaited_once_with(3)
