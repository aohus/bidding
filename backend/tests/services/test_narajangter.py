import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.narajangter import NaraJangterService
from app.schemas.bid import BidAValueItem

@pytest.mark.asyncio
async def test_get_bid_detail_cnstwk():
    service = NaraJangterService()
    bid_no = "20240209001"
    
    # Mock response data for Construction (Cnstwk)
    mock_response_data = {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": [{
                    "bidNtceNo": bid_no,
                    "bssamt": "1000000000",
                    "envCnsrvcst": "500000",
                    "mrfnHealthInsrprm": "100000",
                    "sftyMngcst": "300000"
                }]
            }
        }
    }
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Create a Mock for the response object (Sync methods)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.text = "mock_text"
        mock_response.raise_for_status = MagicMock() 

        mock_get.return_value = mock_response
        
        # We pass bid_type="cnstwk"
        try:
            result = await service.get_bid_a_value(bid_no, bid_type="cnstwk")
        except TypeError:
             pytest.fail("Method signature does not accept bid_type")

        assert result is not None
        assert result.bidNtceNo == bid_no
        assert result.bssamt == "1000000000"
        
        # Verify the correct URL was called
        expected_url = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount"
        
        call_args = mock_get.call_args
        assert str(call_args[0][0]) == expected_url

@pytest.mark.asyncio
async def test_get_bid_detail_servc():
    service = NaraJangterService()
    bid_no = "20240209002"
    
    # Mock response data for Service (Servc)
    mock_response_data = {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": [{
                    "bidNtceNo": bid_no,
                    "bssamt": "500000000",
                }]
            }
        }
    }
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Create a Mock for the response object
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.text = "mock_text"
        mock_response.raise_for_status = MagicMock() 

        mock_get.return_value = mock_response
        
        result = await service.get_bid_a_value(bid_no, bid_type="servc")
        
        assert result is not None
        assert result.bidNtceNo == bid_no
        assert result.bssamt == "500000000"
        
        # Verify the correct URL was called
        expected_url = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcBsisAmount"
        call_args = mock_get.call_args
        assert str(call_args[0][0]) == expected_url