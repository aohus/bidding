from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.bids import (
    KST,
    RESULT_RETRY_COOLDOWN_MINUTES,
    _can_attempt_bid_result_api,
    _parse_bid_datetime,
)


def test_parse_bid_datetime_returns_kst_datetime():
    parsed = _parse_bid_datetime("202602011330")

    assert parsed == datetime(2026, 2, 1, 13, 30, tzinfo=KST)


def test_parse_bid_datetime_handles_dash_colon_format():
    parsed = _parse_bid_datetime("2026-02-01 13:30:00")

    assert parsed == datetime(2026, 2, 1, 13, 30, tzinfo=KST)


def test_parse_bid_datetime_returns_none_for_none():
    assert _parse_bid_datetime(None) is None


def test_parse_bid_datetime_returns_none_for_short_string():
    assert _parse_bid_datetime("20260201") is None


def test_bid_result_api_attempt_starts_30_minutes_before_open():
    openg_dt = datetime(2026, 2, 1, 13, 30, tzinfo=KST)

    assert _can_attempt_bid_result_api(
        openg_dt,
        datetime(2026, 2, 1, 12, 59, tzinfo=KST),
    ) is False
    assert _can_attempt_bid_result_api(
        openg_dt,
        datetime(2026, 2, 1, 13, 0, tzinfo=KST),
    ) is True


def test_bid_result_api_allowed_when_past_open_time():
    openg_dt = datetime(2026, 2, 1, 13, 30, tzinfo=KST)

    assert _can_attempt_bid_result_api(
        openg_dt,
        datetime(2026, 2, 1, 14, 0, tzinfo=KST),
    ) is True


def test_bid_result_api_allowed_when_openg_dt_is_none():
    assert _can_attempt_bid_result_api(None, datetime(2026, 2, 1, 12, 0, tzinfo=KST)) is True


# --- 쿨다운 로직 테스트 (캐시된 빈 결과 기준) ---


def _make_cached(data: list, fetched_at: datetime | None) -> MagicMock:
    m = MagicMock()
    m.data = data
    m.fetched_at = fetched_at
    return m


def _cooldown_still_active(fetched_at: datetime) -> bool:
    """fetched_at 기준 쿨다운이 아직 유효한지 판단 (bids.py 로직과 동일)"""
    fetched_utc = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - fetched_utc
    return age.total_seconds() < RESULT_RETRY_COOLDOWN_MINUTES * 60


def test_cooldown_active_within_10_minutes():
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)

    assert _cooldown_still_active(recent) is True


def test_cooldown_expired_after_10_minutes():
    old = datetime.now(timezone.utc) - timedelta(minutes=11)

    assert _cooldown_still_active(old) is False


def test_cooldown_boundary_exactly_10_minutes():
    boundary = datetime.now(timezone.utc) - timedelta(minutes=10)

    assert _cooldown_still_active(boundary) is False
