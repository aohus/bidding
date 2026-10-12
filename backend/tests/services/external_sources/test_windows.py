import pytest

from app.services.external_sources.windows import (
    MAX_WINDOW_DAYS,
    day_range,
    day_window,
    month_range,
    month_window,
    to_ym,
    to_ymd,
)


class TestWindowBuilders:
    def test_day_window(self):
        assert day_window("20261012") == ("202610120000", "202610122359")

    def test_month_window_31_day_month(self):
        assert month_window("202610") == ("202610010000", "202610312359")

    def test_month_window_30_day_month(self):
        assert month_window("202609") == ("202609010000", "202609302359")

    def test_month_window_february_non_leap(self):
        assert month_window("202602") == ("202602010000", "202602282359")

    def test_month_window_february_leap(self):
        assert month_window("202402") == ("202402010000", "202402292359")

    def test_month_window_december_rolls_year(self):
        assert month_window("202512") == ("202512010000", "202512312359")


class TestConverters:
    def test_to_ymd_truncates(self):
        assert to_ymd("202610121430") == "20261012"

    def test_to_ym_truncates(self):
        assert to_ym("202610121430") == "202610"


class TestDayRange:
    def test_single_day_window(self):
        assert day_range("202610120000", "202610122359") == ("20261012",)

    def test_multi_day_window_is_inclusive(self):
        assert day_range("202610100000", "202610122359") == (
            "20261010",
            "20261011",
            "20261012",
        )

    def test_crosses_month_boundary(self):
        assert day_range("202609300000", "202610012359") == (
            "20260930",
            "20261001",
        )

    def test_reversed_window_returns_empty(self):
        """역순 윈도우를 하루로 보정하면 잘못된 구간이 완료 마킹된다."""
        assert day_range("202610120000", "202610102359") == ()

    def test_too_wide_window_raises(self):
        with pytest.raises(ValueError, match="window too wide"):
            day_range("202001010000", "203001012359")

    def test_exactly_at_cap_is_allowed(self):
        from datetime import date, timedelta

        start = date(2026, 1, 1)
        end = start + timedelta(days=MAX_WINDOW_DAYS - 1)
        days = day_range(
            start.strftime("%Y%m%d") + "0000", end.strftime("%Y%m%d") + "2359"
        )
        assert len(days) == MAX_WINDOW_DAYS


class TestMonthRange:
    def test_single_day_window_yields_its_month(self):
        """수자원 searchDt 는 월 단위 — 하루 윈도우도 그 달을 조회한다."""
        assert month_range("202610120000", "202610122359") == ("202610",)

    def test_spans_multiple_months(self):
        assert month_range("202608150000", "202610052359") == (
            "202608",
            "202609",
            "202610",
        )

    def test_crosses_year_boundary(self):
        assert month_range("202512200000", "202601052359") == (
            "202512",
            "202601",
        )

    def test_reversed_window_returns_empty(self):
        assert month_range("202610120000", "202609102359") == ()
