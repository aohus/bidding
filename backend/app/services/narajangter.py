import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.core.config import settings
from app.schemas.bid import (
    BidApiResponse,
    BidAValueItem,
    BidItem,
    BidResultItem,
    BidSearchParams,
    LicenseLimitItem,
    PrtcptPsblRgnItem,
)

logger = logging.getLogger(__name__)

# 나라장터/data.go.kr 공통 에러코드 (참고자료 "OPEN API 에러코드별 조치방안").
# 주의: 일일 한도 초과는 HTTP 429 가 아니라 코드 22 로 오는 경우가 많다.
SUCCESS_CODE = "00"
NO_DATA_CODE = "03"
RATE_LIMIT_CODES = frozenset({"22"})          # 서비스 요청 제한 횟수 초과
KEY_PROBLEM_CODES = frozenset({"30", "31", "32"})  # 미등록/만료/IP불일치 키

# 마지막 로테이션 후 이 시간이 지나면 첫 키로 복귀 (일일 한도 리셋 반영).
KEY_RESET_SECONDS = 24 * 3600

# 공고목록 조회 API 의 조회기간 상한 (실측: 1개월 초과 시 resultCode 07).
MAX_INQRY_RANGE_DAYS = 31


class NaraJangterApiError(Exception):
    """나라장터 API 가 정상(resultCode=00) 이 아닌 응답을 반환한 경우.

    호출자는 이 예외를 "데이터 없음"과 구분해야 한다. 에러를 빈 결과로
    취급하면 동기화 윈도우가 0건으로 완료 마킹되어 데이터가 영구 누락된다.
    """

    def __init__(self, message: str, code: str = "") -> None:
        self.code = code
        super().__init__(message)


class RateLimitError(NaraJangterApiError):
    """일일 호출 한도 소진 (HTTP 429 또는 resultCode 22).

    보유한 모든 서비스키를 로테이션한 뒤에도 해소되지 않을 때 raise.
    호출자에서 backoff/retry/배치 중단 결정에 사용.
    """


def _extract_error(data: Any) -> Optional[Tuple[str, str]]:
    """응답 봉투에서 (에러코드, 메시지)를 추출합니다. 정상이면 None.

    나라장터/data.go.kr 은 상황에 따라 세 가지 봉투를 사용한다:
      1. {"response": {"header": {"resultCode": "00"|"22"|..., "resultMsg": ...}}}
      2. {"nkoneps.com.response.ResponseError": {"header": {"resultCode": "07", ...}}}
         — 조달청 서비스 자체 파라미터 검증 에러 (07 입력범위 초과, 08 필수값 누락 등)
      3. {"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"returnReasonCode": "22", ...}}}
         — data.go.kr 게이트웨이 에러 (22 한도초과, 30 미등록키 등)
    """
    if not isinstance(data, dict):
        return ("PARSE", "response body is not a JSON object")

    resp = data.get("response")
    if isinstance(resp, dict):
        header = resp.get("header") or {}
        code = str(header.get("resultCode", ""))
        if code == SUCCESS_CODE:
            return None
        return (code, str(header.get("resultMsg", "")))

    svc_err = data.get("nkoneps.com.response.ResponseError")
    if isinstance(svc_err, dict):
        header = svc_err.get("header") or {}
        return (
            str(header.get("resultCode", "")),
            str(header.get("resultMsg", "")),
        )

    gateway_err = data.get("OpenAPI_ServiceResponse")
    if isinstance(gateway_err, dict):
        header = gateway_err.get("cmmMsgHeader") or {}
        return (
            str(header.get("returnReasonCode", "")),
            str(header.get("returnAuthMsg") or header.get("errMsg", "")),
        )

    return ("PARSE", f"unknown response envelope: {sorted(data)[:5]}")


def _items_of(data: dict) -> Tuple[List[dict], dict]:
    """정상 응답 dict 에서 (items, body) 를 꺼냅니다.

    items 가 단건이면 dict 로, 없으면 None 으로 오므로 항상 list 로 정규화한다.
    """
    body = data["response"].get("body") or {}
    items = body.get("items")
    if isinstance(items, dict):
        return [items], body
    if not items:
        return [], body
    return list(items), body


class NaraJangterService:
    """Service for interacting with 나라장터 API."""

    MAX_PAGE_SIZE = 999
    DEFAULT_TIMEOUT_SECONDS = 30.0

    def __init__(self) -> None:
        # 일일 호출 한도 초과 시 V2 → V3 → V4 로 순차 로테이션.
        # 모든 키 소진되면 RateLimitError. KEY_RESET_SECONDS 경과 후 첫 키로 복귀.
        self._service_keys: List[str] = [
            k
            for k in (
                settings.NARAJANGTER_SERVICE_KEY,
                settings.NARAJANGTER_SERVICE_KEY_V2,
                settings.NARAJANGTER_SERVICE_KEY_V3,
                settings.NARAJANGTER_SERVICE_KEY_V4,
            )
            if k
        ]
        self._active_key_idx: int = 0
        self._rotated_at: Optional[datetime] = None

    def _active_key(self) -> str:
        if not self._service_keys:
            raise NaraJangterApiError(
                "NARAJANGTER_SERVICE_KEY 가 설정되지 않았습니다", code="CONFIG"
            )
        return self._service_keys[self._active_key_idx]

    def _maybe_reset_key(self) -> None:
        """마지막 로테이션 후 24h 경과 시 첫 키로 복귀합니다."""
        if self._active_key_idx == 0 or self._rotated_at is None:
            return
        elapsed = (datetime.now(timezone.utc) - self._rotated_at).total_seconds()
        if elapsed >= KEY_RESET_SECONDS:
            logger.info(
                f"narajangter: {int(elapsed)}s since last rotation, "
                f"resetting to key index 0"
            )
            self._active_key_idx = 0
            self._rotated_at = None

    def _rotate_key(self) -> bool:
        """다음 키로 전환. 더 이상 사용 가능한 키가 없으면 False."""
        if self._active_key_idx + 1 >= len(self._service_keys):
            return False
        self._active_key_idx += 1
        self._rotated_at = datetime.now(timezone.utc)
        logger.warning(
            f"narajangter: rotating to key index {self._active_key_idx}"
            f"/{len(self._service_keys) - 1}"
        )
        return True

    BASE_CNST_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"
    BASE_SERV_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"
    # 목록조회(일반) 엔드포인트. PPSSrch 와 달리 inqryDiv=2 가 "입찰공고번호" 조회라
    # 공고번호 단건 조회가 가능하다. PPSSrch 는 inqryDiv 2 가 "개찰일시"이고
    # bidNtceNo 파라미터를 무시하므로 단건 조회에 쓸 수 없다.
    PLAIN_CNST_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"
    PLAIN_SERV_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"
    CNSTWK_BSSAMT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount"
    SERVC_BSSAMT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcBsisAmount"
    PRTCPT_PSBL_RGN_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"
    LICENSE_LIMIT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoLicenseLimit"
    OPENG_RESULT_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoOpengCompt"
    CNSTWK_RESERVE_PRICE_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoCnstwkPreparPcDetail"
    SERVC_RESERVE_PRICE_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoServcPreparPcDetail"
    url_dict = {
        'contract': BASE_CNST_URL,
        'service': BASE_SERV_URL,
    }

    @staticmethod
    def _is_service_type(bid_type: Optional[str]) -> bool:
        return bool(bid_type) and bid_type.lower() in ("servc", "service", "용역")

    async def _request(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Dict[str, Any],
        context: str,
    ) -> Optional[dict]:
        """서비스키 로테이션과 에러 봉투 해석을 포함한 GET.

        Returns:
            정상 응답 dict. 데이터 없음(HTTP 404 또는 resultCode 03)이면 None.

        Raises:
            RateLimitError: 모든 키가 한도 소진 (HTTP 429 / 코드 22)
            NaraJangterApiError: 그 외 모든 비정상 응답
        """
        self._maybe_reset_key()

        while True:
            query = dict(params)
            query["ServiceKey"] = self._active_key()

            try:
                response = await client.get(url, params=query)
            except httpx.HTTPError as exc:
                raise NaraJangterApiError(
                    f"{context}: transport error: {exc}", code="TRANSPORT"
                ) from exc

            if response.status_code == 429:
                logger.warning(
                    f"{context}: HTTP 429 on key idx {self._active_key_idx}"
                )
                if self._rotate_key():
                    continue
                raise RateLimitError(
                    f"{context}: all {len(self._service_keys)} key(s) rate "
                    f"limited (HTTP 429)",
                    code="429",
                )

            if response.status_code == 404:
                logger.info(f"{context}: HTTP 404 → treating as no data")
                return None

            try:
                data = response.json()
            except ValueError:
                raise NaraJangterApiError(
                    f"{context}: HTTP {response.status_code}, non-JSON body: "
                    f"{response.text[:200]}",
                    code="PARSE",
                )

            error = _extract_error(data)
            if error is None:
                return data

            code, message = error

            if code in RATE_LIMIT_CODES:
                logger.warning(
                    f"{context}: rate limit code {code} on key idx "
                    f"{self._active_key_idx}"
                )
                if self._rotate_key():
                    continue
                raise RateLimitError(
                    f"{context}: all {len(self._service_keys)} key(s) exhausted "
                    f"([{code}] {message})",
                    code=code,
                )

            if code in KEY_PROBLEM_CODES:
                if self._rotate_key():
                    continue
                raise NaraJangterApiError(
                    f"{context}: service key rejected ([{code}] {message}). "
                    f"data.go.kr 의 '디코딩' 키를 사용했는지 확인하세요 "
                    f"(인코딩 키를 넣으면 이중 인코딩되어 코드 30 이 됩니다)",
                    code=code,
                )

            if code == NO_DATA_CODE:
                logger.info(f"{context}: resultCode 03 (no data)")
                return None

            raise NaraJangterApiError(f"{context}: [{code}] {message}", code=code)

    async def search_bids(self, work_type, params: BidSearchParams) -> BidApiResponse:
        """Search for bid notices asynchronously."""
        url = self.url_dict[work_type]
        query_params = {
            "inqryDiv": params.inqryDiv,
            "inqryBgnDt": params.inqryBgnDt,
            "inqryEndDt": params.inqryEndDt,
            "numOfRows": params.numOfRows,
            "pageNo": params.pageNo,
            "type": "json",
        }

        if params.prtcptLmtRgnNm:
            query_params["prtcptLmtRgnNm"] = params.prtcptLmtRgnNm
        if params.indstrytyNm:
            query_params["indstrytyNm"] = params.indstrytyNm
        if params.indstrytyCd:
            query_params["indstrytyCd"] = params.indstrytyCd
        if params.presmptPrceBgn:
            query_params["presmptPrceBgn"] = params.presmptPrceBgn
        if params.presmptPrceEnd:
            query_params["presmptPrceEnd"] = params.presmptPrceEnd
        if params.bidClseExcpYn:
            query_params["bidClseExcpYn"] = params.bidClseExcpYn

        context = (
            f"search_bids({work_type}, {params.inqryBgnDt}~{params.inqryEndDt}, "
            f"page={params.pageNo})"
        )
        logger.info(f"NaraJangterService.search_bids: {context}")

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(client, url, query_params, context)

        if data is None:
            return BidApiResponse(
                items=[],
                totalCount=0,
                numOfRows=params.numOfRows,
                pageNo=params.pageNo,
            )

        items_data, body = _items_of(data)
        logger.info(f"Received {len(items_data)} items from NaraJangter API")

        return BidApiResponse(
            items=[BidItem(**item) for item in items_data],
            totalCount=body.get("totalCount", 0),
            numOfRows=body.get("numOfRows", 0),
            pageNo=body.get("pageNo", 1),
        )

    async def get_bid_notice_by_no(
        self, bidNtceNo: str, bid_type: str = "cnstwk"
    ) -> Optional[BidItem]:
        """공고번호로 단건 공고를 조회합니다.

        PPSSrch(나라장터검색조건) 가 아니라 목록조회(일반) 엔드포인트를 쓴다.
        일반 엔드포인트만 inqryDiv=2 가 "입찰공고번호" 조회이며 날짜 범위가
        필요 없다. PPSSrch 는 inqryDiv=2 가 "개찰일시"이고 bidNtceNo 를
        무시하므로 엉뚱한 공고가 반환된다.

        정확히 일치하는 공고가 없으면 None 을 반환한다 (첫 항목 폴백 금지).
        """
        url = (
            self.PLAIN_SERV_URL
            if self._is_service_type(bid_type)
            else self.PLAIN_CNST_URL
        )
        query_params = {
            "inqryDiv": "2",
            "bidNtceNo": bidNtceNo,
            "numOfRows": self.MAX_PAGE_SIZE,
            "pageNo": 1,
            "type": "json",
        }

        context = f"get_bid_notice_by_no({bidNtceNo}, {bid_type})"
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(client, url, query_params, context)

        if data is None:
            return None

        items_data, _ = _items_of(data)
        item = next(
            (d for d in items_data if d.get("bidNtceNo") == bidNtceNo), None
        )
        if item is None:
            logger.info(f"{context}: no exact match among {len(items_data)} items")
            return None

        return BidItem(**item)

    async def get_bid_a_value(
        self, bidNtceNo: str, bid_type: str = "cnstwk"
    ) -> Optional[BidAValueItem]:
        """Get A-value and base amount information for a specific bid notice."""
        query_params = {
            "bidNtceNo": bidNtceNo,
            "inqryDiv": 2,
            "numOfRows": 1,
            "pageNo": 1,
            "type": "json",
        }

        target_url = (
            self.SERVC_BSSAMT_URL
            if self._is_service_type(bid_type)
            else self.CNSTWK_BSSAMT_URL
        )

        context = f"get_bid_a_value({bidNtceNo}, {bid_type})"
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(client, target_url, query_params, context)

        if data is None:
            return None

        items_data, _ = _items_of(data)
        if not items_data:
            logger.info(f"No A-value data found for bidNtceNo: {bidNtceNo}")
            return None

        item = next(
            (d for d in items_data if d.get("bidNtceNo") == bidNtceNo),
            items_data[0],
        )
        return BidAValueItem(**item)

    async def get_prtcpt_psbl_rgn_by_date(
        self,
        inqryBgnDt: str,
        inqryEndDt: str,
        pageNo: int = 1,
        numOfRows: int = MAX_PAGE_SIZE,
    ) -> List[PrtcptPsblRgnItem]:
        """날짜 기준으로 참가가능지역 정보를 조회합니다.

        에러는 빈 리스트로 삼키지 않고 예외로 올린다. 동기화 윈도우가
        0건으로 완료 마킹되면 해당 구간의 지역 정보가 영구 누락되기 때문.
        """
        query_params = {
            "inqryDiv": 1,
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "pageNo": pageNo,
            "numOfRows": numOfRows,
            "type": "json",
        }
        context = (
            f"get_prtcpt_psbl_rgn_by_date({inqryBgnDt}~{inqryEndDt}, "
            f"page={pageNo})"
        )
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(
                client, self.PRTCPT_PSBL_RGN_URL, query_params, context
            )

        if data is None:
            return []
        items_data, _ = _items_of(data)
        return [PrtcptPsblRgnItem(**item) for item in items_data]

    async def get_prtcpt_psbl_rgn_by_bid(
        self,
        bidNtceNo: str,
        bidNtceOrd: str = "000",
    ) -> List[PrtcptPsblRgnItem]:
        """공고번호 기준으로 참가가능지역 정보를 조회합니다."""
        query_params = {
            "inqryDiv": 2,
            "bidNtceNo": bidNtceNo,
            "bidNtceOrd": bidNtceOrd,
            "pageNo": 1,
            "numOfRows": self.MAX_PAGE_SIZE,
            "type": "json",
        }
        context = f"get_prtcpt_psbl_rgn_by_bid({bidNtceNo}-{bidNtceOrd})"
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(
                client, self.PRTCPT_PSBL_RGN_URL, query_params, context
            )

        if data is None:
            return []
        items_data, _ = _items_of(data)
        return [PrtcptPsblRgnItem(**item) for item in items_data]

    async def get_license_limit_by_date(
        self,
        inqryBgnDt: str,
        inqryEndDt: str,
        pageNo: int = 1,
        numOfRows: int = MAX_PAGE_SIZE,
    ) -> List[LicenseLimitItem]:
        """날짜 기준으로 면허제한 정보를 조회합니다.

        get_prtcpt_psbl_rgn_by_date 와 같은 이유로 에러를 삼키지 않는다.
        면허제한 row 가 없으면 업종명 필터 검색에서 공고가 통째로 빠진다.
        """
        query_params = {
            "inqryDiv": 1,
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "pageNo": pageNo,
            "numOfRows": numOfRows,
            "type": "json",
        }
        context = (
            f"get_license_limit_by_date({inqryBgnDt}~{inqryEndDt}, page={pageNo})"
        )
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(
                client, self.LICENSE_LIMIT_URL, query_params, context
            )

        if data is None:
            return []
        items_data, _ = _items_of(data)
        return [LicenseLimitItem(**item) for item in items_data]

    async def get_bid_opening_results(
        self,
        bidNtceNo: str,
        pageNo: int = 1,
        numOfRows: int = MAX_PAGE_SIZE,
    ) -> List[BidResultItem]:
        """개찰결과 조회"""
        query_params = {
            "pageNo": pageNo,
            "numOfRows": numOfRows,
            "bidNtceNo": bidNtceNo,
            "type": "json",
        }
        context = f"get_bid_opening_results({bidNtceNo}, page={pageNo})"
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(
                client, self.OPENG_RESULT_URL, query_params, context
            )

        if data is None:
            return []
        items_data, _ = _items_of(data)
        return [BidResultItem(**item) for item in items_data]

    async def get_reserve_price(
        self,
        bidNtceNo: str,
        openg_dt: str,
        bid_type: str = "cnstwk",
        bidNtceOrd: Optional[str] = None,
    ) -> Optional[dict]:
        """예정가격(plnprc) 상세 정보를 1건 조회합니다.

        Args:
            bidNtceNo: 입찰공고번호
            openg_dt: 개찰일시 (YYYYMMDD~YYYYMMDDHHMM, inqryDiv=2 의 날짜 범위로 사용)
            bid_type: cnstwk/servc
            bidNtceOrd: 입찰차수

        Returns: 첫 페이지 첫 항목 raw dict (없으면 None).
        plnprc, bssamt, bsisPlnprc, rlOpengDt 등이 포함됨.
        복수예가 공고는 보통 15 row 반환되며 plnprc/bssamt 는 동일.
        """
        target_url = (
            self.SERVC_RESERVE_PRICE_URL
            if self._is_service_type(bid_type)
            else self.CNSTWK_RESERVE_PRICE_URL
        )
        # inqryDiv=2 (개찰일 기준) + 개찰일 당일 윈도우.
        # bidNtceNo 필터를 server-side 적용하려면 inqryDiv=2 + 개찰일 범위가 필수.
        ymd = "".join(c for c in openg_dt if c.isdigit())[:8]
        query_params = {
            "pageNo": 1,
            "numOfRows": 20,
            "type": "json",
            "inqryDiv": 2,
            "inqryBgnDt": f"{ymd}0000",
            "inqryEndDt": f"{ymd}2359",
            "bidNtceNo": bidNtceNo,
        }
        if bidNtceOrd:
            query_params["bidNtceOrd"] = bidNtceOrd

        context = f"get_reserve_price({bidNtceNo}, {bid_type}, ymd={ymd})"
        logger.info(context)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await self._request(client, target_url, query_params, context)

        if data is None:
            return None
        items_data, _ = _items_of(data)
        if not items_data:
            return None
        return items_data[0]


narajangter_service = NaraJangterService()
