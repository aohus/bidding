import logging
from typing import Any, Dict, List, Optional

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


class NaraJangterService:
    """Service for interacting with 나라장터 API."""

    BASE_CNST_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"
    BASE_SERV_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"
    CNSTWK_BSSAMT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount"
    SERVC_BSSAMT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcBsisAmount"
    PRTCPT_PSBL_RGN_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"
    LICENSE_LIMIT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoLicenseLimit"
    OPENG_RESULT_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoOpengCompt"
    url_dict = {
        'contract': BASE_CNST_URL,
        'service': BASE_SERV_URL,
    }

    async def search_bids(self, work_type, params: BidSearchParams) -> BidApiResponse:
        url = self.url_dict[work_type]
        
        """Search for bid notices asynchronously."""
        query_params = {
            "inqryDiv": params.inqryDiv,
            "inqryBgnDt": params.inqryBgnDt,
            "inqryEndDt": params.inqryEndDt,
            "numOfRows": params.numOfRows,
            "pageNo": params.pageNo,
            "type": "json",
            "ServiceKey": settings.NARAJANGTER_SERVICE_KEY,
        }
        logger.info(f"NaraJangterService.search_bids called with params: {query_params}")

        # Add optional parameters
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

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url=url, params=query_params)
            response.raise_for_status()

            data = response.json()

            # Check API response status
            if data["response"]["header"]["resultCode"] != "00":
                raise Exception(f"API Error: {data['response']['header']['resultMsg']}")

            body = data["response"]["body"]
            items_data = body.get("items", [])

            # Handle case where items might be a dict with single item
            if isinstance(items_data, dict):
                items_data = [items_data]
            elif items_data is None:
                items_data = []

            logger.info(f"Received {len(items_data)} items from NaraJangter API")
            items = [BidItem(**item) for item in items_data]

            return BidApiResponse(
                items=items,
                totalCount=body.get("totalCount", 0),
                numOfRows=body.get("numOfRows", 0),
                pageNo=body.get("pageNo", 1),
            )

    async def get_bid_a_value(self, bidNtceNo: str, bid_type: str = "cnstwk") -> Optional[BidAValueItem]:
        """Get A-value and base amount information for a specific bid notice."""
        query_params = {
            "bidNtceNo": bidNtceNo,
            "inqryDiv": 2,
            "numOfRows": 1,
            "pageNo": 1,
            "type": "json",
            "ServiceKey": settings.NARAJANGTER_SERVICE_KEY,
        }

        target_url = self.CNSTWK_BSSAMT_URL
        if bid_type and bid_type.lower() in ["servc", "service", "용역"]:
            target_url = self.SERVC_BSSAMT_URL

        logger.info(f"NaraJangterService.get_bid_a_value called for bidNtceNo: {bidNtceNo}, type: {bid_type}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(target_url, params=query_params)

            logger.debug(f"Raw API Response for A-value: {response.text}")

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(f"A-value API returned 404 for bidNtceNo: {bidNtceNo}. Treating as no data found.")
                    return None
                if e.response.status_code == 429:
                    logger.warning(f"A-value API returned 429 (rate limited) for bidNtceNo: {bidNtceNo}.")
                    return None
                raise e

            try:
                data = response.json()
            except ValueError:
                logger.error(f"Failed to parse JSON response. Raw body: {response.text}")
                return None

            if "response" not in data:
                logger.error(f"API response missing 'response' key. Data: {data}")
                return None

            if data["response"]["header"]["resultCode"] != "00":
                logger.error(f"API Error: {data['response']['header']['resultMsg']}")
                return None

            body = data["response"]["body"]
            items_data = body.get("items", [])

            if isinstance(items_data, dict):
                items_data = [items_data]
            elif items_data is None:
                items_data = []

            if not items_data:
                logger.info(f"No A-value data found for bidNtceNo: {bidNtceNo}")
                return None

            item = None
            for item_data in items_data:
                if item_data.get('bidNtceNo') == bidNtceNo:
                    item = item_data
                    break

            if not item and items_data:
                item = items_data[0]

            if not item:
                return None

            return BidAValueItem(**item)

    async def get_prtcpt_psbl_rgn_by_date(
        self,
        inqryBgnDt: str,
        inqryEndDt: str,
        pageNo: int = 1,
        numOfRows: int = 999,
    ) -> List[PrtcptPsblRgnItem]:
        """날짜 기준으로 참가가능지역 정보를 조회합니다."""
        query_params = {
            "inqryDiv": 1,
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "pageNo": pageNo,
            "numOfRows": numOfRows,
            "type": "json",
            "ServiceKey": settings.NARAJANGTER_SERVICE_KEY,
        }
        logger.info(f"get_prtcpt_psbl_rgn_by_date: {inqryBgnDt} ~ {inqryEndDt}, page={pageNo}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.PRTCPT_PSBL_RGN_URL, params=query_params)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return []
                raise e

            try:
                data = response.json()
            except ValueError:
                logger.error(f"Failed to parse region JSON response: {response.text}")
                return []

            if "response" not in data:
                logger.error(f"Region API response missing 'response' key: {data}")
                return []

            if data["response"]["header"]["resultCode"] != "00":
                logger.error(f"Region API Error: {data['response']['header']['resultMsg']}")
                return []

            body = data["response"]["body"]
            items_data = body.get("items", [])

            if isinstance(items_data, dict):
                items_data = [items_data]
            elif items_data is None:
                items_data = []

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
            "numOfRows": 999,
            "type": "json",
            "ServiceKey": settings.NARAJANGTER_SERVICE_KEY,
        }
        logger.info(f"get_prtcpt_psbl_rgn_by_bid: {bidNtceNo}-{bidNtceOrd}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.PRTCPT_PSBL_RGN_URL, params=query_params)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return []
                raise e

            try:
                data = response.json()
            except ValueError:
                logger.error(f"Failed to parse region JSON response: {response.text}")
                return []

            if "response" not in data:
                return []

            if data["response"]["header"]["resultCode"] != "00":
                return []

            body = data["response"]["body"]
            items_data = body.get("items", [])

            if isinstance(items_data, dict):
                items_data = [items_data]
            elif items_data is None:
                items_data = []

            return [PrtcptPsblRgnItem(**item) for item in items_data]


    async def get_license_limit_by_date(
        self,
        inqryBgnDt: str,
        inqryEndDt: str,
        pageNo: int = 1,
        numOfRows: int = 999,
    ) -> List[LicenseLimitItem]:
        """날짜 기준으로 면허제한 정보를 조회합니다."""
        query_params = {
            "inqryDiv": 1,
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "pageNo": pageNo,
            "numOfRows": numOfRows,
            "type": "json",
            "ServiceKey": settings.NARAJANGTER_SERVICE_KEY,
        }
        logger.info(f"get_license_limit_by_date: {inqryBgnDt} ~ {inqryEndDt}, page={pageNo}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.LICENSE_LIMIT_URL, params=query_params)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return []
                raise e

            try:
                data = response.json()
            except ValueError:
                logger.error(f"Failed to parse license limit JSON response: {response.text}")
                return []

            if "response" not in data:
                logger.error(f"License limit API response missing 'response' key: {data}")
                return []

            if data["response"]["header"]["resultCode"] != "00":
                logger.error(f"License limit API Error: {data['response']['header']['resultMsg']}")
                return []

            body = data["response"]["body"]
            items_data = body.get("items", [])

            if isinstance(items_data, dict):
                items_data = [items_data]
            elif items_data is None:
                items_data = []

            return [LicenseLimitItem(**item) for item in items_data]

    async def get_bid_opening_results(
        self,
        bid_ntce_no: str,
        page_no: int = 1,
        num_of_rows: int = 999,
    ) -> List[BidResultItem]:
        """개찰결과 조회"""
        query_params = {
            "serviceKey": settings.NARAJANGTER_SERVICE_KEY,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "bidNtceNo": bid_ntce_no,
            "type": "json",
        }
        logger.info(f"get_bid_opening_results: bidNtceNo={bid_ntce_no}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.OPENG_RESULT_URL, params=query_params)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return []
                raise e

            try:
                data = response.json()
            except ValueError:
                logger.error(f"Failed to parse opening result JSON: {response.text}")
                return []

            if "response" not in data:
                logger.error(f"Opening result API missing 'response' key: {data}")
                return []

            if data["response"]["header"]["resultCode"] != "00":
                logger.error(f"Opening result API Error: {data['response']['header']['resultMsg']}")
                return []

            body = data["response"]["body"]
            items_data = body.get("items", [])

            if isinstance(items_data, dict):
                items_data = [items_data]
            elif items_data is None:
                items_data = []

            return [BidResultItem(**item) for item in items_data]


narajangter_service = NaraJangterService()
