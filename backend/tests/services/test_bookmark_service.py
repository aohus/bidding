from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.services.bookmark_service import (
    _dashboard_response,
    _dashboard_sort_col,
    _dashboard_status_filter,
    _normalize_bid_notice_ord,
)

KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# _normalize_bid_notice_ord
# ---------------------------------------------------------------------------


def test_normalize_bid_notice_ord_none():
    assert _normalize_bid_notice_ord(None) == "000"


def test_normalize_bid_notice_ord_empty_string():
    assert _normalize_bid_notice_ord("") == "000"


def test_normalize_bid_notice_ord_whitespace_only():
    assert _normalize_bid_notice_ord("   ") == "000"


def test_normalize_bid_notice_ord_returns_stripped_value():
    assert _normalize_bid_notice_ord("  001  ") == "001"


def test_normalize_bid_notice_ord_already_normalized():
    assert _normalize_bid_notice_ord("000") == "000"
    assert _normalize_bid_notice_ord("002") == "002"


# ---------------------------------------------------------------------------
# _dashboard_response
# ---------------------------------------------------------------------------


def _make_dashboard_item(**kwargs) -> MagicMock:
    defaults = {
        "bookmark_id": uuid4(),
        "user_id": uuid4(),
        "bid_notice_no": "12345678",
        "bid_notice_name": "테스트 공고",
        "bid_notice_ord": "000",
        "status": "bid_completed",
        "bid_price": None,
        "notes": None,
        "created_at": datetime(2026, 1, 1, tzinfo=KST),
        "updated_at": None,
        "bid_close_dt": None,
        "openg_dt": None,
        "openg_completed": False,
        "actual_bid_price": None,
        "bid_rate": None,
        "rank_value": None,
        "total_bidders": None,
        "winning_bid_price": None,
        "winning_bid_rate": None,
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def test_dashboard_response_rank_none_when_rank_value_is_none():
    row = _make_dashboard_item(rank_value=None)
    response = _dashboard_response(row)
    assert response.rank is None


def test_dashboard_response_rank_str_when_positive():
    row = _make_dashboard_item(rank_value=1)
    response = _dashboard_response(row)
    assert response.rank == "1"


def test_dashboard_response_rank_str_when_negative():
    row = _make_dashboard_item(rank_value=-3)
    response = _dashboard_response(row)
    assert response.rank == "-3"


def test_dashboard_response_maps_core_fields():
    uid = uuid4()
    bid_id = uuid4()
    row = _make_dashboard_item(
        bookmark_id=bid_id,
        user_id=uid,
        bid_notice_no="99999999",
        bid_notice_name="공고명",
        status="interested",
        openg_completed=True,
        total_bidders=5,
    )
    response = _dashboard_response(row)
    assert response.bookmark_id == bid_id
    assert response.user_id == uid
    assert response.bid_notice_no == "99999999"
    assert response.bid_notice_name == "공고명"
    assert response.status == "interested"
    assert response.openg_completed is True
    assert response.total_bidders == 5


# ---------------------------------------------------------------------------
# _dashboard_sort_col
# ---------------------------------------------------------------------------

from app.models.user import BookmarkDashboardItem


def test_dashboard_sort_col_known_fields():
    assert _dashboard_sort_col("openg_dt") is BookmarkDashboardItem.openg_dt
    assert _dashboard_sort_col("bid_close_dt") is BookmarkDashboardItem.bid_close_dt
    assert _dashboard_sort_col("created_at") is BookmarkDashboardItem.created_at
    assert _dashboard_sort_col("rank") is BookmarkDashboardItem.rank_value


def test_dashboard_sort_col_unknown_falls_back_to_created_at():
    assert _dashboard_sort_col("nonexistent") is BookmarkDashboardItem.created_at
    assert _dashboard_sort_col("") is BookmarkDashboardItem.created_at


# ---------------------------------------------------------------------------
# _dashboard_status_filter
# ---------------------------------------------------------------------------


def test_dashboard_status_filter_completed_returns_expr():
    expr = _dashboard_status_filter("completed", "202601011200", "20260101")
    assert expr is not None


def test_dashboard_status_filter_today_returns_expr():
    expr = _dashboard_status_filter("today", "202601011200", "20260101")
    assert expr is not None


def test_dashboard_status_filter_upcoming_returns_expr():
    expr = _dashboard_status_filter("upcoming", "202601011200", "20260101")
    assert expr is not None


def test_dashboard_status_filter_waiting_returns_expr():
    expr = _dashboard_status_filter("waiting", "202601011200", "20260101")
    assert expr is not None


def test_dashboard_status_filter_unknown_key_returns_none():
    result = _dashboard_status_filter("invalid_key", "202601011200", "20260101")
    assert result is None
