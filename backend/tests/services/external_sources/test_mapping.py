"""날짜/금액 정규화 테스트.

소스마다 날짜 표기가 전부 다르다 (실측):
  kdhc   '20261008'              (YYYYMMDD)
  kogas  '2026-10-16 10:00'      (분까지)
  kepco  '2026-10-01 13:40:51'   (초까지)
  kra    '20260425' + '18:10'    (날짜/시각 분리 필드)
  kwater '-'                     (값 없음 sentinel)
  lh     '20261001'
"""

import pytest

from app.services.external_sources.mapping import (
    NoticeRecord,
    ResultRecord,
    combine_dt14,
    to_dt14,
    to_int,
)


class TestToDt14:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("20261008", "202610080000"),
            ("2026-10-16 10:00", "202610161000"),
            ("2026-10-01 13:40:51", "202610011340"),
            ("2014.12.01", "201412010000"),
            ("202610161030", "202610161030"),
            ("2026-10-12T16:32:10+09:00", "202610121632"),
        ],
    )
    def test_normalizes_known_formats(self, raw, expected):
        assert to_dt14(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "-", "   ", "없음", "2026"])
    def test_returns_none_for_unusable_values(self, raw):
        """8자리 미만이면 유효한 날짜를 만들 수 없으므로 None.

        '202610' 을 '202610000000' 으로 패딩하면 존재하지 않는 날짜(10월 0일)가
        되어 범위 비교를 조용히 망친다.
        """
        assert to_dt14(raw) is None


class TestCombineDt14:
    def test_combines_date_and_time(self):
        assert combine_dt14("20260425", "18:10") == "202604251810"

    def test_combines_date_and_time_without_colon(self):
        assert combine_dt14("20260425", "1810") == "202604251810"

    def test_date_only_when_time_missing(self):
        assert combine_dt14("20260425", None) == "202604250000"
        assert combine_dt14("20260425", "") == "202604250000"

    def test_none_when_date_missing(self):
        assert combine_dt14(None, "18:10") is None

    def test_ignores_seconds_in_time(self):
        assert combine_dt14("20260425", "18:10:59") == "202604251810"


class TestToInt:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("128142913", 128142913),
            ("152,338,000", 152338000),
            (364280000, 364280000),
            ("1000.0", 1000),
            ("  42  ", 42),
        ],
    )
    def test_parses_amounts(self, raw, expected):
        assert to_int(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "-", "비공개", "0"])
    def test_returns_none_for_unusable_values(self, raw):
        """0 도 None 으로 본다 — 금액 0 은 '미공개'의 관용 표현이다."""
        assert to_int(raw) is None


class TestRecordsAreImmutable:
    def test_notice_record_is_frozen(self):
        rec = NoticeRecord(source="kdhc", notice_no="1", notice_ord="00", data={})
        with pytest.raises(Exception):
            rec.title = "x"

    def test_result_record_is_frozen(self):
        rec = ResultRecord(source="kra", notice_no="1", notice_ord="000", data={})
        with pytest.raises(Exception):
            rec.bidder_nm = "x"

    def test_notice_record_defaults_are_none(self):
        rec = NoticeRecord(source="kdhc", notice_no="1", notice_ord="00", data={})
        assert rec.title is None
        assert rec.presmpt_prce is None

    def test_result_record_seq_defaults_to_zero(self):
        rec = ResultRecord(source="kra", notice_no="1", notice_ord="000", data={})
        assert rec.seq == 0
