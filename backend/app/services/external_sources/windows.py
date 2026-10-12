"""동기화 윈도우(YYYYMMDDHHMM) → 소스별 조회 단위 변환.

소스마다 조회 파라미터의 시간 해상도가 다르다:
  * 날짜 범위: LH(tndrbidRegDtStart/End), 지역난방(startDate/endDate),
              가스공사(DOCDATE_START/END), 전력개발포털(noticeBeginDate/EndDate)
  * 날짜 단건: 마사회(notice_date / open_date) — 하루씩 순회해야 한다
  * 월 단건  : 수자원(searchDt=YYYYMM) — 월 단위로만 조회된다
"""

from datetime import date, datetime, timedelta
from typing import Tuple

# 윈도우 문자열의 앞 8자리가 날짜(YYYYMMDD)다.
_DATE_LEN = 8
_MONTH_LEN = 6
# 폭주 방지. 수동 백필에서도 한 윈도우가 이보다 넓을 이유가 없다.
MAX_WINDOW_DAYS = 400


def to_ymd(window_value: str) -> str:
    """YYYYMMDDHHMM → YYYYMMDD."""
    return window_value[:_DATE_LEN]


def to_ym(window_value: str) -> str:
    """YYYYMMDDHHMM → YYYYMM."""
    return window_value[:_MONTH_LEN]


def _parse(window_value: str) -> date:
    return datetime.strptime(to_ymd(window_value), "%Y%m%d").date()


def day_range(window_start: str, window_end: str) -> Tuple[str, ...]:
    """윈도우를 YYYYMMDD 일자 목록으로 펼칩니다 (양끝 포함).

    역순 윈도우는 빈 튜플을 반환한다 (조용히 하루로 보정하면 잘못된 구간이
    완료 마킹된다).
    """
    start, end = _parse(window_start), _parse(window_end)
    if end < start:
        return ()
    span = (end - start).days + 1
    if span > MAX_WINDOW_DAYS:
        raise ValueError(
            f"window too wide: {window_start}~{window_end} ({span} days, "
            f"max {MAX_WINDOW_DAYS})"
        )
    return tuple(
        (start + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(span)
    )


def day_window(ymd: str) -> Tuple[str, str]:
    """YYYYMMDD → (YYYYMMDD0000, YYYYMMDD2359) 일별 윈도우."""
    return f"{ymd}0000", f"{ymd}2359"


def month_window(ym: str) -> Tuple[str, str]:
    """YYYYMM → (YYYYMM010000, YYYYMM<말일>2359) 월별 윈도우.

    수자원처럼 월 단위로만 조회되는 소스의 동기화 마커로 쓴다.
    """
    year, month = int(ym[:4]), int(ym[4:6])
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = next_month_first - timedelta(days=1)
    return f"{ym}010000", f"{last_day.strftime('%Y%m%d')}2359"


def month_range(window_start: str, window_end: str) -> Tuple[str, ...]:
    """윈도우를 YYYYMM 월 목록으로 펼칩니다 (양끝 포함).

    수자원 searchDt 는 월 단위라, 하루짜리 윈도우도 그 달 전체를 조회한다.
    """
    start, end = _parse(window_start), _parse(window_end)
    if end < start:
        return ()

    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return tuple(months)
