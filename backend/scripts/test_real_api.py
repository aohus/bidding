import asyncio
import os
import sys
import logging

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.narajangter import NaraJangterService
from app.schemas.bid import BidSearchParams
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_api():
    print(f"Service Key: {settings.NARAJANGTER_SERVICE_KEY[:5]}...")
    
    if settings.NARAJANGTER_SERVICE_KEY.startswith("your_actual"):
        print("Error: Please set a valid NARAJANGTER_SERVICE_KEY in .env")
        return

    service = NaraJangterService()
    
    # 1. Search for recent bids (Construction)
    from datetime import datetime, timedelta
    now = datetime.now()
    start_dt = (now - timedelta(days=7)).strftime("%Y%m%d0000")
    end_dt = now.strftime("%Y%m%d2359")
    
    params = BidSearchParams(
        inqryDiv="1",
        inqryBgnDt=start_dt,
        inqryEndDt=end_dt,
        numOfRows=10,
        pageNo=1
    )
    
    print("Searching for recent bids...")
    try:
        search_result = await service.search_bids(params)
        print(f"Found {search_result.totalCount} bids.")
        
        if not search_result.items:
            print("No items found to test detail API.")
            return

        # 2. Try to get detail for the first item
        target_bid = search_result.items[0]
        print(f"Testing detail API for Bid No: {target_bid.bidNtceNo} ({target_bid.bidNtceNm})")
        
        # We need to guess type or try both if not known. 
        # Search API returns info but maybe not explicitly 'cnstwk' vs 'servc' type code in the simplified item?
        # Let's try 'cnstwk' first as default.
        
        detail = await service.get_bid_a_value(target_bid.bidNtceNo, bid_type="cnstwk")
        if detail:
            print("Successfully retrieved Construction Detail:")
            print(detail.model_dump_json(indent=2))
        else:
            print("Failed to get Construction Detail (or it might be a Service bid).")
            # Try service
            print("Retrying with Service type...")
            detail_servc = await service.get_bid_a_value(target_bid.bidNtceNo, bid_type="servc")
            if detail_servc:
                print("Successfully retrieved Service Detail:")
                print(detail_servc.model_dump_json(indent=2))
            else:
                print("Failed to get Service Detail as well.")

    except Exception as e:
        print(f"API Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_api())
