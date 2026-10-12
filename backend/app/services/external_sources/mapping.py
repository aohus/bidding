"""외부기관 응답 → 저장 레코드 공통 타입과 값 정규화.

소스마다 날짜/금액 표기가 전혀 달라서(실측 기준은 테스트 docstring 참조)
정규화를 한 곳에 모은다. 레코드는 frozen dataclass — 매퍼가 만든 값을
하류에서 변형하지 않는다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# 유효한 날짜를 만들려면 최소 YYYYMMDD(8자리)가 필요하다. 그보다 짧으면
# 패딩해도 존재하지 않는 날짜가 되어 범위 비교를 조용히 망친다.
_MIN_DATE_DIGITS = 8
_DT14_LENGTH = 12


def _digits(value: Any) -> str:
    if value is None:
        return ""
    return "".join(c for c in str(value) if c.isdigit())


def to_dt14(value: Any) -> Optional[str]:
    """날짜 문자열을 YYYYMMDDHHMM 으로 정규화합니다. 불가하면 None.

    구분자(-, ., :, T, 공백)는 무시하고 숫자만 취한 뒤 12자리로 맞춘다.
    8자리(날짜만)면 0000 을 붙이고, 12자리 초과(초/타임존 포함)는 자른다.
    """
    digits = _digits(value)
    if len(digits) < _MIN_DATE_DIGITS:
        return None
    return digits[:_DT14_LENGTH].ljust(_DT14_LENGTH, "0")


def combine_dt14(date_value: Any, time_value: Any) -> Optional[str]:
    """분리된 날짜/시각 필드를 YYYYMMDDHHMM 으로 합칩니다 (마사회 형식).

    시각이 없으면 0000 으로 둔다. 날짜가 없으면 None.
    """
    date_digits = _digits(date_value)
    if len(date_digits) < _MIN_DATE_DIGITS:
        return None
    time_digits = _digits(time_value)[:4]
    return (date_digits[:8] + time_digits).ljust(_DT14_LENGTH, "0")


def to_int(value: Any) -> Optional[int]:
    """금액 문자열을 int 로 변환합니다. 불가하거나 0 이면 None.

    0 을 None 으로 보는 이유: 외부기관은 미공개 금액을 0 또는 빈 값으로
    내려보내므로 '0원 공고'와 구분할 실익이 없다.
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        parsed = int(float(text))
    except (TypeError, ValueError):
        return None
    return parsed or None


@dataclass(frozen=True)
class NoticeRecord:
    """external_bid_notices 한 행에 대응하는 불변 레코드."""

    source: str
    notice_no: str
    notice_ord: str
    data: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
    institution: Optional[str] = None
    work_div: Optional[str] = None
    cntrct_mthd: Optional[str] = None
    rgst_dt: Optional[str] = None
    bid_close_dt: Optional[str] = None
    openg_dt: Optional[str] = None
    presmpt_prce: Optional[int] = None
    status: Optional[str] = None


@dataclass(frozen=True)
class ResultRecord:
    """external_bid_results 한 행에 대응하는 불변 레코드."""

    source: str
    notice_no: str
    notice_ord: str
    data: Dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    title: Optional[str] = None
    bidder_nm: Optional[str] = None
    bidder_amt: Optional[int] = None
    status_nm: Optional[str] = None
    openg_dt: Optional[str] = None


@dataclass(frozen=True)
class SourceFetch:
    """어댑터 한 번의 수집 결과.

    api_calls 를 함께 반환해 스케줄러가 호출 예산을 집계할 수 있게 한다.
    """

    notices: Tuple[NoticeRecord, ...] = ()
    results: Tuple[ResultRecord, ...] = ()
    api_calls: int = 0
