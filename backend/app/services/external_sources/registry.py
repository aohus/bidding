"""외부기관 소스 레지스트리.

새 기관을 추가할 때 손댈 곳은 어댑터 모듈 하나와 이 파일의 SOURCES 뿐이다.
"""

from typing import Dict, Protocol, Tuple, runtime_checkable

from app.services.external_sources.kdhc import kdhc_source
from app.services.external_sources.kepco import kepco_source
from app.services.external_sources.kogas import kogas_source
from app.services.external_sources.kra import kra_source
from app.services.external_sources.kwater import kwater_source
from app.services.external_sources.lh import lh_source
from app.services.external_sources.mapping import SourceFetch


@runtime_checkable
class ExternalBidSource(Protocol):
    """외부기관 수집 어댑터 계약."""

    #: external_bid_notices.source 에 저장되는 식별자
    source: str
    #: 사람이 읽는 기관명
    name: str
    #: 'day' | 'month' — 스케줄러가 윈도우 폭을 정할 때 쓴다.
    #: 수자원은 searchDt 가 월 단위라 일별 윈도우로 돌리면 같은 달을
    #: 매일 재조회하게 되므로 월 단위로 묶어야 한다.
    granularity: str

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        """윈도우(YYYYMMDDHHMM) 구간의 공고/결과를 수집합니다.

        에러는 예외로 올린다 — 빈 결과로 삼키면 호출자가 윈도우를 완료
        마킹해 해당 구간이 영구 누락된다.
        """
        ...


SOURCES: Dict[str, ExternalBidSource] = {
    src.source: src
    for src in (
        lh_source,
        kwater_source,
        kdhc_source,
        kra_source,
        kogas_source,
        kepco_source,
    )
}


def get_source(source_id: str) -> ExternalBidSource:
    try:
        return SOURCES[source_id]
    except KeyError:
        raise KeyError(
            f"unknown external source '{source_id}' "
            f"(known: {sorted(SOURCES)})"
        ) from None


def source_ids() -> Tuple[str, ...]:
    return tuple(SOURCES)
