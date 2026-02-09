import logging
from typing import Any, Dict, List, Optional

import httpx
from app.core.config import settings
from app.schemas.bid import BidApiResponse, BidAValueItem, BidItem, BidSearchParams

logger = logging.getLogger(__name__)

class NaraJangterService:
    """Service for interacting with 나라장터 API."""
    
    BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"
    CNSTWK_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"
    # AVALUE_URL removed as per spec
    CNSTWK_BSSAMT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount"
    SERVC_BSSAMT_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcBsisAmount"
    
    async def search_bids(self, params: BidSearchParams) -> BidApiResponse:
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
        if params.presmptPrceBgn:
            query_params["presmptPrceBgn"] = params.presmptPrceBgn
        if params.presmptPrceEnd:
            query_params["presmptPrceEnd"] = params.presmptPrceEnd
        if params.bidClseExcpYn:
            query_params["bidClseExcpYn"] = params.bidClseExcpYn
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=query_params)
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
            
            # Log raw response for debugging
            logger.debug(f"Raw API Response for A-value: {response.text}")
            
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError:
                logger.error(f"Failed to parse JSON response. Raw body: {response.text}")
                return None
            
            # Check if 'response' key exists
            if "response" not in data:
                logger.error(f"API response missing 'response' key. Data: {data}")
                return None

            # Check API response status
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
                
            # Assume the first item is the correct one
            item = None
            for item_data in items_data:
                if item_data.get('bidNtceNo') == bidNtceNo:
                    item = item_data
                    break
            
            # If not found by exact match, take the first one if available (API sometimes returns related items)
            if not item and items_data:
                item = items_data[0]
            
            if not item:
                return None
            
            # Map API response fields to BidAValueItem
            # Pydantic model will handle extra fields (ignore them) and missing optional fields (None)
            # We just pass the dict directly as keys match
            return BidAValueItem(**item)


narajangter_service = NaraJangterService()
