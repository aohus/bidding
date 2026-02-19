import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.narajangter import NaraJangterService
from app.schemas.bid import (
    BidAValueItem,
    BidApiResponse,
    BidResultItem,
    BidSearchParams,
    LicenseLimitItem,
    PrtcptPsblRgnItem,
)
from tests.conftest import (
    make_mock_response,
    make_success_response,
    make_error_response,
    make_http_status_error,
)


@pytest.fixture
def service():
    return NaraJangterService()


# ---------------------------------------------------------------------------
# Class constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_max_page_size_exists(self):
        assert hasattr(NaraJangterService, "MAX_PAGE_SIZE")
        assert NaraJangterService.MAX_PAGE_SIZE == 999

    def test_default_timeout_exists(self):
        assert hasattr(NaraJangterService, "DEFAULT_TIMEOUT_SECONDS")
        assert NaraJangterService.DEFAULT_TIMEOUT_SECONDS == 30.0


# ---------------------------------------------------------------------------
# _parse_api_response helper
# ---------------------------------------------------------------------------

class TestParseApiResponse:
    def setup_method(self):
        self.service = NaraJangterService()

    def test_success_returns_items_list(self):
        data = make_success_response([{"bidNtceNo": "A001"}])
        items, body = self.service._parse_api_response(data, "test")
        assert items == [{"bidNtceNo": "A001"}]
        assert body is not None

    def test_single_dict_normalized_to_list(self):
        data = make_success_response({"bidNtceNo": "A002"})
        items, body = self.service._parse_api_response(data, "test")
        assert items == [{"bidNtceNo": "A002"}]

    def test_none_items_returns_empty(self):
        data = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": None, "totalCount": 0},
            }
        }
        items, body = self.service._parse_api_response(data, "test")
        assert items == []

    def test_empty_list_returns_empty(self):
        data = make_success_response([])
        items, body = self.service._parse_api_response(data, "test")
        assert items == []

    def test_missing_response_key_returns_empty(self):
        items, body = self.service._parse_api_response({"error": "bad"}, "test")
        assert items == []
        assert body is None

    def test_error_result_code_returns_empty(self):
        data = make_error_response("99", "FAIL")
        items, body = self.service._parse_api_response(data, "test")
        assert items == []
        assert body is None

    def test_body_is_returned(self):
        data = make_success_response([{"x": 1}])
        items, body = self.service._parse_api_response(data, "test")
        assert "totalCount" in body


# ---------------------------------------------------------------------------
# get_bid_a_value
# ---------------------------------------------------------------------------

class TestGetBidAValue:
    @pytest.mark.asyncio
    async def test_success_cnstwk(self, service):
        items = [{"bidNtceNo": "20240209001", "bssamt": "1000000000"}]
        mock_resp = make_mock_response(json_data=make_success_response(items))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("20240209001", bid_type="cnstwk")

        assert result is not None
        assert result.bidNtceNo == "20240209001"
        assert result.bssamt == "1000000000"

    @pytest.mark.asyncio
    async def test_success_servc(self, service):
        items = [{"bidNtceNo": "20240209002", "bssamt": "500000000"}]
        mock_resp = make_mock_response(json_data=make_success_response(items))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("20240209002", bid_type="servc")

        assert result is not None
        assert result.bidNtceNo == "20240209002"

    @pytest.mark.asyncio
    async def test_404_returns_none(self, service):
        error = make_http_status_error(404)
        mock_resp = make_mock_response(raise_for_status_error=error)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("NOTFOUND")

        assert result is None

    @pytest.mark.asyncio
    async def test_429_returns_none(self, service):
        error = make_http_status_error(429)
        mock_resp = make_mock_response(raise_for_status_error=error)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("RATELIMITED")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self, service):
        mock_resp = make_mock_response(json_raises=True)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("BADJSON")

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_response_key_returns_none(self, service):
        mock_resp = make_mock_response(json_data={"error": "something"})

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("NORESPKEY")

        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_code_returns_none(self, service):
        mock_resp = make_mock_response(json_data=make_error_response())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("APIERR")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_items_returns_none(self, service):
        mock_resp = make_mock_response(json_data=make_success_response([]))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("EMPTY")

        assert result is None

    @pytest.mark.asyncio
    async def test_single_dict_item(self, service):
        """items가 list가 아닌 dict일 때도 정상 처리"""
        item = {"bidNtceNo": "SINGLE", "bssamt": "100"}
        data = make_success_response(item)  # dict, not list
        mock_resp = make_mock_response(json_data=data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_a_value("SINGLE")

        assert result is not None
        assert result.bidNtceNo == "SINGLE"


# ---------------------------------------------------------------------------
# get_prtcpt_psbl_rgn_by_date
# ---------------------------------------------------------------------------

class TestGetPrtcptPsblRgnByDate:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [
            {"bidNtceNo": "B001", "bidNtceOrd": "000", "prtcptPsblRgnNm": "서울"},
        ]
        mock_resp = make_mock_response(json_data=make_success_response(items))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_prtcpt_psbl_rgn_by_date(
                "202402010000", "202402012359"
            )

        assert len(result) == 1
        assert result[0].bidNtceNo == "B001"

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, service):
        error = make_http_status_error(404)
        mock_resp = make_mock_response(raise_for_status_error=error)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_prtcpt_psbl_rgn_by_date("x", "y")

        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self, service):
        mock_resp = make_mock_response(json_raises=True)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_prtcpt_psbl_rgn_by_date("x", "y")

        assert result == []

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self, service):
        mock_resp = make_mock_response(json_data=make_error_response())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_prtcpt_psbl_rgn_by_date("x", "y")

        assert result == []

    @pytest.mark.asyncio
    async def test_default_num_of_rows_is_999(self, service):
        """기본 numOfRows가 999인지 확인"""
        mock_resp = make_mock_response(json_data=make_success_response([]))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp) as mock_get:
            await service.get_prtcpt_psbl_rgn_by_date("x", "y")

            call_kwargs = mock_get.call_args
            params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
            assert params["numOfRows"] == 999


# ---------------------------------------------------------------------------
# get_prtcpt_psbl_rgn_by_bid
# ---------------------------------------------------------------------------

class TestGetPrtcptPsblRgnByBid:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [
            {"bidNtceNo": "B001", "bidNtceOrd": "000", "prtcptPsblRgnNm": "경기"},
        ]
        mock_resp = make_mock_response(json_data=make_success_response(items))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_prtcpt_psbl_rgn_by_bid("B001")

        assert len(result) == 1
        assert result[0].prtcptPsblRgnNm == "경기"

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, service):
        error = make_http_status_error(404)
        mock_resp = make_mock_response(raise_for_status_error=error)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_prtcpt_psbl_rgn_by_bid("NOTFOUND")

        assert result == []


# ---------------------------------------------------------------------------
# get_license_limit_by_date
# ---------------------------------------------------------------------------

class TestGetLicenseLimitByDate:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [{"bidNtceNo": "L001", "lcnsLmtNm": "건설업"}]
        mock_resp = make_mock_response(json_data=make_success_response(items))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_license_limit_by_date("x", "y")

        assert len(result) == 1
        assert result[0].bidNtceNo == "L001"

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, service):
        error = make_http_status_error(404)
        mock_resp = make_mock_response(raise_for_status_error=error)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_license_limit_by_date("x", "y")

        assert result == []

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self, service):
        mock_resp = make_mock_response(json_data=make_error_response())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_license_limit_by_date("x", "y")

        assert result == []


# ---------------------------------------------------------------------------
# get_bid_opening_results
# ---------------------------------------------------------------------------

class TestGetBidOpeningResults:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [{"bidNtceNo": "R001", "prcbdrBizno": "123-45-67890"}]
        mock_resp = make_mock_response(json_data=make_success_response(items))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_opening_results("R001")

        assert len(result) == 1
        assert result[0].bidNtceNo == "R001"

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, service):
        error = make_http_status_error(404)
        mock_resp = make_mock_response(raise_for_status_error=error)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_opening_results("NOTFOUND")

        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self, service):
        mock_resp = make_mock_response(json_raises=True)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_opening_results("BADJSON")

        assert result == []

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self, service):
        mock_resp = make_mock_response(json_data=make_error_response())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_opening_results("ERR")

        assert result == []

    @pytest.mark.asyncio
    async def test_missing_response_key_returns_empty(self, service):
        mock_resp = make_mock_response(json_data={"no_response": True})

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await service.get_bid_opening_results("NOKEY")

        assert result == []

    @pytest.mark.asyncio
    async def test_custom_page_size(self, service):
        """커스텀 numOfRows가 API에 전달되는지 확인"""
        mock_resp = make_mock_response(json_data=make_success_response([]))

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp) as mock_get:
            await service.get_bid_opening_results("X", numOfRows=50)

            call_kwargs = mock_get.call_args
            params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
            assert params["numOfRows"] == 50


# ---------------------------------------------------------------------------
# search_bids
# ---------------------------------------------------------------------------

class TestSearchBids:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [
            {
                "bidNtceNo": "S001",
                "bidNtceOrd": "000",
                "bidNtceNm": "테스트공고",
                "ntceInsttNm": "조달청",
            },
        ]
        data = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {
                    "items": items,
                    "totalCount": 1,
                    "numOfRows": 100,
                    "pageNo": 1,
                },
            }
        }
        mock_resp = make_mock_response(json_data=data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            params = BidSearchParams(
                inqryDiv="1",
                inqryBgnDt="202402010000",
                inqryEndDt="202402012359",
            )
            result = await service.search_bids("contract", params)

        assert isinstance(result, BidApiResponse)
        assert result.totalCount == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_api_error_raises(self, service):
        """search_bids는 API 에러 시 Exception을 raise"""
        mock_resp = make_mock_response(json_data=make_error_response())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            params = BidSearchParams(
                inqryDiv="1",
                inqryBgnDt="202402010000",
                inqryEndDt="202402012359",
            )
            with pytest.raises(Exception, match="API Error"):
                await service.search_bids("contract", params)
