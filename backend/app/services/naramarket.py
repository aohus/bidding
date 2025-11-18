import httpx
from typing import Dict, Any, List
from app.core.config import settings
from app.schemas.bid import BidSearchParams, BidApiResponse, BidItem


class NaraMarketService:
    """Service for interacting with 나라장터 API."""
    
    BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"
    
    async def search_bids(self, params: BidSearchParams) -> BidApiResponse:
        """Search for bid notices asynchronously."""
        query_params = {
            "inqryDiv": params.inqryDiv,
            "inqryBgnDt": params.inqryBgnDt,
            "inqryEndDt": params.inqryEndDt,
            "numOfRows": params.numOfRows,
            "pageNo": params.pageNo,
            "type": "json",
            "ServiceKey": settings.NARAMARKET_SERVICE_KEY,
        }
        
        # Add optional parameters
        if params.prtcptLmtRgnCd:
            query_params["prtcptLmtRgnCd"] = params.prtcptLmtRgnCd
        if params.presmptPrceBgn:
            query_params["presmptPrceBgn"] = params.presmptPrceBgn
        if params.presmptPrceEnd:
            query_params["presmptPrceEnd"] = params.presmptPrceEnd
        
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
            
            items = [BidItem(**item) for item in items_data]
            
            return BidApiResponse(
                items=items,
                totalCount=body.get("totalCount", 0),
                numOfRows=body.get("numOfRows", 0),
                pageNo=body.get("pageNo", 1),
            )


naramarket_service = NaraMarketService()