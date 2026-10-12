"""외부기관 data.go.kr API 공통 XML 클라이언트.

나라장터(JSON)와 달리 외부기관 6개 소스는 모두 XML 로 응답한다. 응답 구조에
실측으로 확인된 편차가 있어 파싱을 한 곳에 모아둔다:

  * LH 는 <body><item> 구조로 <items> 래퍼가 없다.
  * LH 는 EUC-KR 이다. expat 이 EUC-KR 을 모르므로 직접 디코딩해야 한다.
  * 빈 결과는 <items/> 로 오고, 값 없는 필드는 <TAG/> 로 온다.
  * 에러 봉투는 <response><header> 와 게이트웨이 <cmmMsgHeader> 두 종류다.

에러 처리 원칙은 나라장터 클라이언트와 같다: **에러를 빈 결과로 삼키지
않는다**. 삼키면 동기화 윈도우가 0건으로 완료 마킹되어 데이터가 영구 누락된다.
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.services.service_key_rotator import (
    NoServiceKeyError,
    ServiceKeyRotator,
)

logger = logging.getLogger(__name__)

SUCCESS_CODE = "00"
NO_DATA_CODES = frozenset({"03"})
RATE_LIMIT_CODES = frozenset({"22"})
KEY_PROBLEM_CODES = frozenset({"30", "31", "32"})

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_PAGE_SIZE = 500
# 한 윈도우가 이보다 많은 페이지를 요구하면 윈도우 설계가 잘못된 것이다.
MAX_PAGES = 50

_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
_PROLOG_ENCODING = re.compile(rb'encoding\s*=\s*["\']([\w-]+)["\']', re.IGNORECASE)


class ExternalApiError(Exception):
    """외부기관 API 가 정상(resultCode=00)이 아닌 응답을 반환한 경우."""

    def __init__(self, message: str, code: str = "") -> None:
        self.code = code
        super().__init__(message)


class ExternalRateLimitError(ExternalApiError):
    """일일 호출 한도 소진 (HTTP 429 또는 resultCode 22). 모든 키 소진 후 raise."""


@dataclass(frozen=True)
class Envelope:
    """파싱된 응답 봉투 (불변)."""

    code: str
    message: str
    items: Tuple[Dict[str, Optional[str]], ...]
    total_count: int


def decode_body(raw: bytes) -> str:
    """응답 바이트를 str 로 디코딩하고 XML 선언을 제거합니다.

    XML 선언을 지우는 이유: encoding 선언이 남은 str 을 ElementTree 에 넘기면
    "Unicode strings with encoding declaration are not supported" 로 죽는다.
    """
    match = _PROLOG_ENCODING.search(raw[:200])
    declared = match.group(1).decode("ascii", "ignore").lower() if match else None

    candidates = [c for c in (declared, "utf-8", "euc-kr") if c]
    for codec in candidates:
        try:
            text = raw.decode(codec)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        # 모든 코덱 실패 — 손실을 감수하고라도 파싱은 시도한다.
        text = raw.decode("utf-8", "replace")

    return _XML_DECL.sub("", text, count=1).strip()


def _element_to_dict(element: ET.Element) -> Dict[str, Optional[str]]:
    """<item> 엘리먼트를 {태그: 값} dict 로 변환합니다.

    빈 엘리먼트(<TAG/>)와 공백만 있는 값은 None 으로 정규화한다 — 하류에서
    빈 문자열과 '값 없음'을 구분하지 않아도 되게 한다.
    """
    result: Dict[str, Optional[str]] = {}
    for child in element:
        text = (child.text or "").strip()
        result[child.tag] = text or None
    return result


def _extract_items(root: ET.Element) -> Tuple[Dict[str, Optional[str]], ...]:
    """body 아래에서 item 목록을 추출합니다.

    <body><items><item> (대부분) 과 <body><item> (LH) 를 모두 지원한다.
    body 하위 어디서든 item 을 찾으므로 <script/> 같은 잡음 엘리먼트에 영향받지 않는다.
    """
    body = root.find("body")
    if body is None:
        return ()
    return tuple(_element_to_dict(item) for item in body.iter("item"))


def _extract_total_count(root: ET.Element) -> int:
    node = root.find("./body/totalCount")
    text = (node.text or "").strip() if node is not None else ""
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        return 0


def parse_xml_envelope(raw: bytes) -> Envelope:
    """XML 응답을 Envelope 으로 파싱합니다.

    Raises:
        ExternalApiError(code="PARSE"): XML 이 아니거나 구조가 깨진 경우.
    """
    text = decode_body(raw)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ExternalApiError(
            f"malformed XML response: {exc} :: {text[:200]}", code="PARSE"
        ) from exc

    # 1) 표준 봉투: <response><header><resultCode>
    header = root.find("header")
    if header is not None:
        code = (header.findtext("resultCode") or "").strip()
        message = (header.findtext("resultMsg") or "").strip()
        return Envelope(
            code=code,
            message=message,
            items=_extract_items(root),
            total_count=_extract_total_count(root),
        )

    # 2) 게이트웨이 봉투: <OpenAPI_ServiceResponse><cmmMsgHeader>
    gateway = root.find(".//cmmMsgHeader")
    if gateway is not None:
        return Envelope(
            code=(gateway.findtext("returnReasonCode") or "").strip(),
            message=(
                gateway.findtext("returnAuthMsg")
                or gateway.findtext("errMsg")
                or ""
            ).strip(),
            items=(),
            total_count=0,
        )

    raise ExternalApiError(
        f"unknown response envelope: root=<{root.tag}>", code="PARSE"
    )


class DataGoKrXmlClient:
    """서비스키 로테이션을 포함한 data.go.kr XML GET 클라이언트."""

    def __init__(
        self,
        rotator: Optional[ServiceKeyRotator] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.rotator = rotator or ServiceKeyRotator(
            settings.data_go_kr_service_keys
        )
        self.timeout = timeout

    async def fetch(
        self,
        url: str,
        params: Dict[str, Any],
        context: str,
    ) -> Optional[Envelope]:
        """GET 후 Envelope 을 반환합니다.

        Returns:
            정상 응답 Envelope. 데이터 없음(HTTP 404 또는 resultCode 03)이면 None.

        Raises:
            ExternalRateLimitError: 모든 키가 한도 소진 (HTTP 429 / 코드 22)
            ExternalApiError: 그 외 모든 비정상 응답
        """
        self.rotator.maybe_reset()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                try:
                    key = self.rotator.active_key()
                except NoServiceKeyError as exc:
                    raise ExternalApiError(str(exc), code="CONFIG") from exc

                query = dict(params)
                query["serviceKey"] = key

                try:
                    response = await client.get(url, params=query)
                except httpx.HTTPError as exc:
                    raise ExternalApiError(
                        f"{context}: transport error: {exc}", code="TRANSPORT"
                    ) from exc

                if response.status_code == 429:
                    logger.warning(
                        f"{context}: HTTP 429 on key idx "
                        f"{self.rotator.active_idx}"
                    )
                    if self.rotator.rotate():
                        continue
                    raise ExternalRateLimitError(
                        f"{context}: all {self.rotator.key_count} key(s) rate "
                        f"limited (HTTP 429)",
                        code="429",
                    )

                if response.status_code == 403:
                    # 해당 서비스에 활용신청되지 않은 키 (실측: LOCAL 키).
                    logger.warning(
                        f"{context}: HTTP 403 on key idx "
                        f"{self.rotator.active_idx}"
                    )
                    if self.rotator.rotate():
                        continue
                    raise ExternalApiError(
                        f"{context}: HTTP 403 on all {self.rotator.key_count} "
                        f"key(s). 해당 서비스에 활용신청되지 않은 키일 수 "
                        f"있습니다 (data.go.kr 에서 서비스별 활용신청 필요)",
                        code="403",
                    )

                if response.status_code == 404:
                    logger.info(f"{context}: HTTP 404 → treating as no data")
                    return None

                envelope = parse_xml_envelope(response.content)
                code = envelope.code

                if code == SUCCESS_CODE:
                    return envelope

                if code in RATE_LIMIT_CODES:
                    logger.warning(
                        f"{context}: rate limit code {code} on key idx "
                        f"{self.rotator.active_idx}"
                    )
                    if self.rotator.rotate():
                        continue
                    raise ExternalRateLimitError(
                        f"{context}: all {self.rotator.key_count} key(s) "
                        f"exhausted ([{code}] {envelope.message})",
                        code=code,
                    )

                if code in KEY_PROBLEM_CODES:
                    if self.rotator.rotate():
                        continue
                    raise ExternalApiError(
                        f"{context}: service key rejected "
                        f"([{code}] {envelope.message}). data.go.kr 의 "
                        f"'디코딩' 키인지, 해당 서비스에 활용신청됐는지 확인하세요",
                        code=code,
                    )

                if code in NO_DATA_CODES:
                    logger.info(f"{context}: resultCode {code} (no data)")
                    return None

                raise ExternalApiError(
                    f"{context}: [{code}] {envelope.message}", code=code
                )

    async def fetch_paged(
        self,
        url: str,
        params: Dict[str, Any],
        context: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: int = MAX_PAGES,
    ) -> Tuple[Tuple[Dict[str, Optional[str]], ...], int]:
        """전 페이지를 순회해 item 전체와 사용한 API 호출 수를 반환합니다.

        에러는 전파한다 — 부분 결과를 성공으로 반환하면 호출자가 윈도우를
        완료 마킹해 누락된 페이지가 영구 유실된다.

        max_pages 상한에 걸리면 경고를 남긴다. 조용히 끊으면 '전부 수집됨'으로
        오인된다.
        """
        collected: list = []
        calls = 0

        for page in range(1, max_pages + 1):
            query = dict(params)
            query["pageNo"] = page
            query["numOfRows"] = page_size

            envelope = await self.fetch(url, query, f"{context} page={page}")
            calls += 1

            if envelope is None or not envelope.items:
                break

            collected.extend(envelope.items)

            if len(envelope.items) < page_size:
                break
            if envelope.total_count and len(collected) >= envelope.total_count:
                break
        else:
            logger.warning(
                f"{context}: hit max_pages={max_pages} "
                f"({len(collected)} items collected) — 수집이 잘렸을 수 있습니다"
            )

        return tuple(collected), calls
