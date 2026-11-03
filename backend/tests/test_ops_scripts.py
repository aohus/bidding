"""운영 스크립트(backfill_bid_sub_datasets, check_narajangter_endpoints) 테스트."""
import importlib.util
import pathlib
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


backfill = load("backfill_bid_sub_datasets")
check = load("check_narajangter_endpoints")


class TestBackfill:
    def test_past_days_order_and_count(self):
        days = backfill.past_days(3, datetime(2026, 11, 3, 15, 0))
        assert days == ["20261101", "20261102", "20261103"]

    @pytest.mark.parametrize("bad", [0, -1, 10_000])
    def test_past_days_rejects_out_of_range(self, bad):
        with pytest.raises(SystemExit):
            backfill.past_days(bad)

    @pytest.mark.asyncio
    async def test_dataset_saves_each_page_until_short_page(self):
        full = [object()] * backfill.NaraJangterService.MAX_PAGE_SIZE
        fetch = AsyncMock(side_effect=[full, [object()]])
        save = AsyncMock()
        with patch.object(backfill, "PAGE_DELAY_SECONDS", 0):
            total, ok = await backfill.backfill_dataset("x", fetch, save, "db", "20261103", False)
        assert ok and total == len(full) + 1
        assert save.await_count == 2
        fetch.assert_any_await("202611030000", "202611032359", 1)
        fetch.assert_any_await("202611030000", "202611032359", 2)

    @pytest.mark.asyncio
    async def test_dry_run_does_not_save(self):
        fetch = AsyncMock(return_value=[object()])
        save = AsyncMock()
        total, ok = await backfill.backfill_dataset("x", fetch, save, None, "20261103", True)
        assert (total, ok) == (1, True)
        save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failure_reports_not_ok(self):
        fetch = AsyncMock(side_effect=RuntimeError("boom"))
        total, ok = await backfill.backfill_dataset("x", fetch, AsyncMock(), None, "20261103", False)
        assert (total, ok) == (0, False)

    @pytest.mark.asyncio
    async def test_run_continues_after_failure_and_returns_false(self):
        good = AsyncMock(return_value=[])
        bad = AsyncMock(side_effect=RuntimeError("x"))
        datasets = [("a", bad, AsyncMock()), ("b", good, AsyncMock())]
        with patch.object(backfill, "PAGE_DELAY_SECONDS", 0):
            ok = await backfill.run(["20261102", "20261103"], True, datasets=datasets)
        assert ok is False
        assert good.await_count == 2


class TestBackfillMarksAndRedacts:
    @pytest.mark.asyncio
    async def test_successful_day_marks_sub_datasets_synced(self):
        ds = [("a", AsyncMock(return_value=[]), AsyncMock()) for _ in range(3)]
        with patch.object(backfill, "PAGE_DELAY_SECONDS", 0), patch.object(
            backfill, "mark_day_done", AsyncMock()
        ) as mark:
            ok = await backfill.run(["20261102"], False, db="db", datasets=ds)
        assert ok is True
        mark.assert_awaited_once_with("db", "20261102", [0, 0, 0])

    @pytest.mark.asyncio
    async def test_failed_day_or_dry_run_does_not_mark(self):
        bad = [("a", AsyncMock(side_effect=RuntimeError("x")), AsyncMock())] * 3
        good = [("a", AsyncMock(return_value=[]), AsyncMock())] * 3
        with patch.object(backfill, "PAGE_DELAY_SECONDS", 0), patch.object(
            backfill, "mark_day_done", AsyncMock()
        ) as mark:
            await backfill.run(["20261102"], False, db="db", datasets=bad)
            await backfill.run(["20261102"], True, db=None, datasets=good)
        mark.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failure_output_is_redacted(self, capsys):
        fetch = AsyncMock(side_effect=RuntimeError("bad ?ServiceKey=KEY123&x=1"))
        await backfill.backfill_dataset("x", fetch, AsyncMock(), None, "20261103", True)
        out = capsys.readouterr().out
        assert "KEY123" not in out and "ServiceKey=***" in out

    @pytest.mark.asyncio
    async def test_mark_day_done_targets_daily_window(self):
        with patch(
            "app.services.bid_data_service.bid_data_service.mark_sub_datasets_synced",
            AsyncMock(),
        ) as m:
            await backfill.mark_day_done("db", "20261102", [1, 2, 3])
        m.assert_awaited_once_with("db", "202611020000", "202611022359", 1, 2, 3)


class TestEndpointCheck:
    def test_covers_all_app_operations(self):
        names = {n for n, _, _ in check.OPERATIONS}
        assert len(names) == 13
        assert all(n.endswith("02") for n in names)
        assert "getBidPblancListInfoAtchFileInfo02" in names

    def test_urls_match_operation_names(self):
        for name, url, _ in check.OPERATIONS:
            assert url.endswith("/" + name)

    def test_atch_probe_sends_bsns_div_cd(self):
        build = next(b for n, _, b in check.OPERATIONS if n == "getBidPblancListInfoAtchFileInfo02")
        assert build(datetime(2026, 11, 3, 12, 0))["bsnsDivCd"] == "3"

    def test_redact_hides_keys(self):
        assert "SECRET" not in check.redact("url?ServiceKey=SECRET", ["SECRET"])

    @pytest.mark.asyncio
    async def test_failure_message_is_redacted(self):
        with patch.object(
            check.narajangter_service, "_request",
            AsyncMock(side_effect=RuntimeError("bad ServiceKey=KEY123")),
        ), patch.object(
            type(check.narajangter_service), "_service_keys",
            new_callable=lambda: property(lambda self: ["KEY123"]),
        ):
            ok, detail = await check.check_operation("op", "u", lambda n: {}, datetime.now())
        assert not ok and "KEY123" not in detail

    @pytest.mark.asyncio
    async def test_main_exit_code_nonzero_on_failure(self):
        results = [(True, "OK")] * 12 + [(False, "x")]
        with patch.object(check, "check_operation", AsyncMock(side_effect=results)), \
             patch.object(check.asyncio, "sleep", AsyncMock()):
            assert await check.main() == 1

    @pytest.mark.asyncio
    async def test_main_exit_code_zero_when_all_ok(self):
        with patch.object(check, "check_operation", AsyncMock(return_value=(True, "OK"))), \
             patch.object(check.asyncio, "sleep", AsyncMock()):
            assert await check.main() == 0
