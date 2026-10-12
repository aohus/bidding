"""한국마사회 전자입찰 공고정보(API182) + 낙찰정보(API183).

명세: docs/external-bid-api.md (4. 한국마사회)
실측(2026-10-12) 주의사항:
  * 문서는 응답 필드를 bCode 라고 쓰지만 실제 응답은 **BCode** 다.
  * 날짜 필터가 범위가 아니라 **단건**(notice_date / open_date)이라
    윈도우를 하루씩 순회해야 한다.
  * 업무구분/계약방법/상태가 **코드**로 와서 명칭 변환이 필요하다
    (낙찰정보 API183 은 반대로 명칭 문자열을 준다).
"""

import logging
from typing import List, Optional

from app.models.external_bid import SOURCE_KRA
from app.services.external_sources.base import DataGoKrXmlClient
from app.services.external_sources.mapping import (
    NoticeRecord,
    ResultRecord,
    SourceFetch,
    combine_dt14,
)
from app.services.external_sources.windows import day_range

logger = logging.getLogger(__name__)

AGENCY_NAME = "한국마사회"
NOTICE_URL = "https://apis.data.go.kr/B551015/API182/E-noticeInfo"
RESULT_URL = "https://apis.data.go.kr/B551015/API183_1/E-successInfo_1"

# 문서(API182) 기준 코드표. 미등록 코드는 원본 코드를 그대로 노출한다.
WORK_TYPE_NAMES = {
    "01": "시설공사",
    "02": "기술용역",
    "03": "일반용역",
    "05": "매각",
}
CONT_METHOD_NAMES = {
    "1": "일반경쟁",
    "2": "지명경쟁",
    "3": "제한경쟁",
    "4": "수의계약",
}
STATUS_NAMES = {
    "00": "작성중",
    "10": "품의중",
    "18": "품의반송",
    "19": "품의완료",
    "20": "공고중",
    "30": "심사중",
    "97": "완료(재입찰)",
    "98": "완료(유찰)",
    "99": "완료(낙찰)",
}


def _decode(table: dict, code: Optional[str]) -> Optional[str]:
    """코드를 명칭으로 변환합니다. 미등록 코드는 원본을 유지합니다.

    조용히 None 으로 떨구면 신규 코드가 추가됐을 때 데이터가 사라진다.
    """
    if not code:
        return None
    return table.get(code, code)


class KraSource:
    source = SOURCE_KRA
    name = AGENCY_NAME
    granularity = "day"

    def __init__(self, client: Optional[DataGoKrXmlClient] = None) -> None:
        self._client = client or DataGoKrXmlClient()

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        notices: List[NoticeRecord] = []
        results: List[ResultRecord] = []
        calls = 0

        for day in day_range(window_start, window_end):
            notice_items, notice_calls = await self._client.fetch_paged(
                NOTICE_URL, {"notice_date": day}, f"kra-notice({day})"
            )
            calls += notice_calls
            notices.extend(self._to_notice(item) for item in notice_items)

            result_items, result_calls = await self._client.fetch_paged(
                RESULT_URL, {"open_date": day}, f"kra-result({day})"
            )
            calls += result_calls
            results.extend(self._to_result(item) for item in result_items)

        return SourceFetch(
            notices=tuple(notices),
            results=tuple(results),
            api_calls=calls,
        )

    def _to_notice(self, item: dict) -> NoticeRecord:
        return NoticeRecord(
            source=self.source,
            notice_no=item.get("BCode") or "",
            notice_ord="000",
            title=item.get("bidName"),
            institution=item.get("noticeAuth") or AGENCY_NAME,
            work_div=_decode(WORK_TYPE_NAMES, item.get("workType")),
            cntrct_mthd=_decode(CONT_METHOD_NAMES, item.get("contMethod")),
            rgst_dt=combine_dt14(
                item.get("noticeDate"), item.get("noticeTime")
            ),
            bid_close_dt=combine_dt14(
                item.get("bidEndDate"), item.get("bidEndTime")
            ),
            openg_dt=combine_dt14(item.get("openDate"), item.get("openTime")),
            status=_decode(STATUS_NAMES, item.get("status")),
            data=dict(item),
        )

    def _to_result(self, item: dict) -> ResultRecord:
        """낙찰정보(API183). 업체명/금액은 제공되지 않는다 — 결과구분명만 온다."""
        return ResultRecord(
            source=self.source,
            notice_no=item.get("BCode") or "",
            notice_ord="000",
            seq=0,
            title=item.get("bidName"),
            status_nm=item.get("statusNm"),
            openg_dt=combine_dt14(item.get("openDate"), item.get("openTime")),
            data=dict(item),
        )


kra_source = KraSource()
