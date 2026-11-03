from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.bid import BidSearchParams
from app.services.narajangter import (
    KEY_RESET_SECONDS,
    NaraJangterApiError,
    NaraJangterService,
    RateLimitError,
    _extract_error,
    _items_of,
)
from tests.conftest import (
    make_error_response,
    make_gateway_error_response,
    make_mock_response,
    make_service_error_response,
    make_success_response,
)


@pytest.fixture
def service():
    svc = NaraJangterService()
    svc._service_keys = ["key1"]
    svc._active_key_idx = 0
    svc._rotated_at = None
    return svc


@pytest.fixture
def multikey_service():
    svc = NaraJangterService()
    svc._service_keys = ["key1", "key2", "key3"]
    svc._active_key_idx = 0
    svc._rotated_at = None
    return svc


def patch_get(*responses):
    """httpx.AsyncClient.get 을 순차 응답으로 패치합니다."""
    if len(responses) == 1:
        return patch(
            "httpx.AsyncClient.get", new_callable=AsyncMock,
            return_value=responses[0],
        )
    return patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock,
        side_effect=list(responses),
    )


# ---------------------------------------------------------------------------
# Class constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_max_page_size_exists(self):
        assert NaraJangterService.MAX_PAGE_SIZE == 999

    def test_default_timeout_exists(self):
        assert NaraJangterService.DEFAULT_TIMEOUT_SECONDS == 30.0

    def test_single_notice_lookup_uses_plain_endpoints(self):
        """단건 조회는 PPSSrch 가 아닌 목록조회(일반) 엔드포인트여야 한다.

        PPSSrch 는 inqryDiv=2 가 '개찰일시'이고 bidNtceNo 를 무시한다.
        """
        assert NaraJangterService.PLAIN_CNST_URL.endswith(
            "getBidPblancListInfoCnstwk02"
        )
        assert NaraJangterService.PLAIN_SERV_URL.endswith(
            "getBidPblancListInfoServc02"
        )
        assert "PPSSrch" not in NaraJangterService.PLAIN_CNST_URL
        assert "PPSSrch" not in NaraJangterService.PLAIN_SERV_URL


# ---------------------------------------------------------------------------
# _extract_error — 세 가지 응답 봉투
# ---------------------------------------------------------------------------

class TestExtractError:
    def test_success_returns_none(self):
        assert _extract_error(make_success_response([])) is None

    def test_standard_envelope_error(self):
        code, msg = _extract_error(make_error_response("99", "BOOM"))
        assert code == "99"
        assert msg == "BOOM"

    def test_service_error_envelope(self):
        """조달청 자체 검증 에러 (조회기간 초과 등)."""
        code, msg = _extract_error(make_service_error_response("07"))
        assert code == "07"
        assert "입력범위값" in msg

    def test_gateway_error_envelope_quota(self):
        """일일 한도 초과는 게이트웨이 봉투 + 코드 22 로 온다."""
        code, msg = _extract_error(make_gateway_error_response("22"))
        assert code == "22"

    def test_gateway_error_envelope_bad_key(self):
        code, msg = _extract_error(
            make_gateway_error_response("30", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
        )
        assert code == "30"

    def test_unknown_envelope(self):
        code, _ = _extract_error({"something": "else"})
        assert code == "PARSE"

    def test_non_dict(self):
        code, _ = _extract_error(["not", "a", "dict"])
        assert code == "PARSE"


# ---------------------------------------------------------------------------
# _items_of
# ---------------------------------------------------------------------------

class TestItemsOf:
    def test_list_items(self):
        items, body = _items_of(make_success_response([{"bidNtceNo": "A"}]))
        assert items == [{"bidNtceNo": "A"}]
        assert "totalCount" in body

    def test_single_dict_normalized_to_list(self):
        items, _ = _items_of(make_success_response({"bidNtceNo": "B"}))
        assert items == [{"bidNtceNo": "B"}]

    def test_none_items(self):
        data = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": None, "totalCount": 0},
            }
        }
        items, _ = _items_of(data)
        assert items == []

    def test_missing_body(self):
        data = {"response": {"header": {"resultCode": "00"}}}
        items, body = _items_of(data)
        assert items == []
        assert body == {}


# ---------------------------------------------------------------------------
# _request — 키 로테이션 / 에러 분류
# ---------------------------------------------------------------------------

class TestRequestDoesNotLeakServiceKey:
    @pytest.mark.asyncio
    async def test_transport_error_message_and_chain_are_redacted(self, service):
        import httpx

        err = httpx.ConnectError("boom https://h/x?ServiceKey=key1&a=1")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=err):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")

        assert "key1" not in str(exc.value)
        assert "ConnectError" in str(exc.value)
        assert exc.value.__cause__ is None

    @pytest.mark.asyncio
    async def test_non_json_body_is_redacted(self, service):
        resp = make_mock_response(status_code=500, text="oops ?ServiceKey=key1&x")
        resp.json.side_effect = ValueError("no json")
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")
        assert "key1" not in str(exc.value)

    @pytest.mark.asyncio
    async def test_envelope_message_is_redacted(self, service):
        bad = make_mock_response(json_data=make_error_response("99", "echo ServiceKey=key1"))
        with patch_get(bad):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")
        assert "key1" not in str(exc.value)


class TestRequestRotation:
    @pytest.mark.asyncio
    async def test_http_429_rotates_then_succeeds(self, multikey_service):
        limited = make_mock_response(status_code=429, text="rate limited")
        ok = make_mock_response(json_data=make_success_response([{"bidNtceNo": "X"}]))

        with patch_get(limited, ok):
            result = await multikey_service.get_bid_opening_results("X")

        assert len(result) == 1
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_code_22_rotates_then_succeeds(self, multikey_service):
        """일일 한도(코드 22)도 429 와 동일하게 로테이션 대상이다."""
        quota = make_mock_response(json_data=make_gateway_error_response("22"))
        ok = make_mock_response(json_data=make_success_response([{"bidNtceNo": "X"}]))

        with patch_get(quota, ok):
            result = await multikey_service.get_bid_opening_results("X")

        assert len(result) == 1
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_all_keys_exhausted_raises_rate_limit(self, multikey_service):
        quota = make_mock_response(json_data=make_gateway_error_response("22"))

        with patch_get(quota, quota, quota):
            with pytest.raises(RateLimitError) as exc:
                await multikey_service.get_bid_opening_results("X")

        assert multikey_service._active_key_idx == 2
        assert "exhausted" in str(exc.value)

    @pytest.mark.asyncio
    async def test_single_key_429_raises_immediately(self, service):
        limited = make_mock_response(status_code=429, text="rate limited")

        with patch_get(limited):
            with pytest.raises(RateLimitError):
                await service.get_bid_opening_results("X")

    @pytest.mark.asyncio
    async def test_bad_key_code_30_raises_with_hint(self, service):
        bad = make_mock_response(
            status_code=403,
            json_data=make_gateway_error_response(
                "30", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"
            ),
        )

        with patch_get(bad):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")

        assert exc.value.code == "30"
        assert "디코딩" in str(exc.value)

    @pytest.mark.asyncio
    async def test_bare_http_403_rotates_then_succeeds(self, multikey_service):
        """본문 없는 403 = 해당 서비스에 활용신청 안 된 키 → 다음 키로 넘어간다.

        실측: LOCAL_NARAJANGTER_SERVICE_KEY 로 외부기관 6개 서비스를 호출하면
        에러 봉투 없이 bare 403 이 온다. 로테이션하지 않으면 폴백이 죽는다.
        """
        forbidden = make_mock_response(status_code=403, json_raises=True, text="403")
        ok = make_mock_response(json_data=make_success_response([{"bidNtceNo": "X"}]))

        with patch_get(forbidden, ok):
            result = await multikey_service.get_bid_opening_results("X")

        assert len(result) == 1
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_bare_http_403_all_keys_raises_with_hint(self, service):
        forbidden = make_mock_response(status_code=403, json_raises=True, text="403")

        with patch_get(forbidden):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")

        assert exc.value.code == "403"
        assert "활용신청" in str(exc.value)

    @pytest.mark.asyncio
    async def test_non_403_non_json_still_raises_parse_error(self, service):
        """403 이 아닌 비-JSON 응답은 기존처럼 PARSE 에러여야 한다 (로테이션 금지)."""
        broken = make_mock_response(status_code=500, json_raises=True, text="boom")

        with patch_get(broken):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")

        assert exc.value.code == "PARSE"

    @pytest.mark.asyncio
    async def test_rate_limit_error_is_api_error_subclass(self):
        assert issubclass(RateLimitError, NaraJangterApiError)

    def test_key_pool_comes_from_shared_settings_pool(self):
        """나라장터 키 풀은 config 의 공용 풀(LOCAL 폴백 포함)에서 온다."""
        from types import SimpleNamespace

        fake = SimpleNamespace(
            data_go_kr_service_keys=["v1", "v2", "local"]
        )
        with patch("app.services.narajangter.settings", fake):
            svc = NaraJangterService()

        assert svc._service_keys == ["v1", "v2", "local"]

    def test_key_reset_after_24h(self, multikey_service):
        multikey_service._active_key_idx = 2
        multikey_service._rotated_at = datetime.now(timezone.utc) - timedelta(
            seconds=KEY_RESET_SECONDS + 60
        )

        multikey_service._maybe_reset_key()

        assert multikey_service._active_key_idx == 0
        assert multikey_service._rotated_at is None

    def test_key_not_reset_before_24h(self, multikey_service):
        multikey_service._active_key_idx = 2
        multikey_service._rotated_at = datetime.now(timezone.utc) - timedelta(
            seconds=KEY_RESET_SECONDS - 60
        )

        multikey_service._maybe_reset_key()

        assert multikey_service._active_key_idx == 2

    def test_rotate_records_timestamp(self, multikey_service):
        assert multikey_service._rotated_at is None
        assert multikey_service._rotate_key() is True
        assert multikey_service._rotated_at is not None

    def test_rotate_exhausted_returns_false(self, service):
        assert service._rotate_key() is False

    def test_missing_key_config_raises(self):
        svc = NaraJangterService()
        svc._service_keys = []
        with pytest.raises(NaraJangterApiError) as exc:
            svc._active_key()
        assert exc.value.code == "CONFIG"


# ---------------------------------------------------------------------------
# _request — 데이터 없음 vs 에러 구분
# ---------------------------------------------------------------------------

class TestRequestNoDataVsError:
    @pytest.mark.asyncio
    async def test_http_404_is_no_data(self, service):
        resp = make_mock_response(status_code=404, text="not found")
        with patch_get(resp):
            assert await service.get_bid_opening_results("X") == []

    @pytest.mark.asyncio
    async def test_result_code_03_is_no_data(self, service):
        resp = make_mock_response(json_data=make_error_response("03", "NODATA"))
        with patch_get(resp):
            assert await service.get_bid_opening_results("X") == []

    @pytest.mark.asyncio
    async def test_generic_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("01", "App Error"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")
        assert exc.value.code == "01"

    @pytest.mark.asyncio
    async def test_non_json_raises(self, service):
        resp = make_mock_response(json_raises=True, text="<html>gateway</html>")
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")
        assert exc.value.code == "PARSE"

    @pytest.mark.asyncio
    async def test_unknown_envelope_raises(self, service):
        resp = make_mock_response(json_data={"unexpected": 1})
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_bid_opening_results("X")


# ---------------------------------------------------------------------------
# get_bid_notice_by_no — 단건 조회
# ---------------------------------------------------------------------------

class TestGetBidNoticeByNo:
    @pytest.mark.asyncio
    async def test_uses_plain_endpoint_and_inqrydiv_2(self, service):
        item = {
            "bidNtceNo": "R26BK01665863",
            "bidNtceOrd": "000",
            "bidNtceNm": "테스트 공고",
            "ntceInsttNm": "경기도 양평군",
        }
        resp = make_mock_response(json_data=make_success_response([item]))

        with patch_get(resp) as mock_get:
            result = await service.get_bid_notice_by_no("R26BK01665863")

            url = mock_get.call_args[0][0]
            params = mock_get.call_args[1]["params"]

        assert result is not None
        assert result.bidNtceNo == "R26BK01665863"
        assert url == NaraJangterService.PLAIN_CNST_URL
        assert params["inqryDiv"] == "2"
        assert params["bidNtceNo"] == "R26BK01665863"

    @pytest.mark.asyncio
    async def test_does_not_send_date_range(self, service):
        """조회기간을 보내면 안 된다 — 1개월 초과 시 resultCode 07 로 실패한다.

        기존 구현은 2025-01-01~2027-12-31 을 보내 항상 실패했다.
        """
        resp = make_mock_response(json_data=make_success_response([]))

        with patch_get(resp) as mock_get:
            await service.get_bid_notice_by_no("R26BK01665863")
            params = mock_get.call_args[1]["params"]

        assert "inqryBgnDt" not in params
        assert "inqryEndDt" not in params

    @pytest.mark.asyncio
    async def test_service_type_uses_plain_serv_url(self, service):
        resp = make_mock_response(json_data=make_success_response([]))

        with patch_get(resp) as mock_get:
            await service.get_bid_notice_by_no("X", bid_type="servc")
            url = mock_get.call_args[0][0]

        assert url == NaraJangterService.PLAIN_SERV_URL

    @pytest.mark.asyncio
    async def test_no_exact_match_returns_none(self, service):
        """다른 공고가 섞여 와도 첫 항목으로 폴백하면 안 된다.

        폴백하면 엉뚱한 공고 데이터가 그 공고번호로 저장된다.
        """
        others = [
            {
                "bidNtceNo": "R26BK09999999",
                "bidNtceOrd": "000",
                "bidNtceNm": "다른 공고",
                "ntceInsttNm": "다른 기관",
            }
        ]
        resp = make_mock_response(json_data=make_success_response(others))

        with patch_get(resp):
            result = await service.get_bid_notice_by_no("R26BK01665863")

        assert result is None

    @pytest.mark.asyncio
    async def test_picks_exact_match_among_many(self, service):
        items = [
            {
                "bidNtceNo": "R26BK00000001",
                "bidNtceOrd": "000",
                "bidNtceNm": "A",
                "ntceInsttNm": "기관",
            },
            {
                "bidNtceNo": "R26BK01665863",
                "bidNtceOrd": "000",
                "bidNtceNm": "정답",
                "ntceInsttNm": "기관",
            },
        ]
        resp = make_mock_response(json_data=make_success_response(items))

        with patch_get(resp):
            result = await service.get_bid_notice_by_no("R26BK01665863")

        assert result is not None
        assert result.bidNtceNm == "정답"

    @pytest.mark.asyncio
    async def test_empty_result_returns_none(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp):
            assert await service.get_bid_notice_by_no("X") is None

    @pytest.mark.asyncio
    async def test_parses_v12_new_fields(self, service):
        """참고자료 v1.2 신규 항목이 스키마에 담겨야 한다."""
        item = {
            "bidNtceNo": "R26BK01665863",
            "bidNtceOrd": "000",
            "bidNtceNm": "테스트",
            "ntceInsttNm": "기관",
            "sucsfbidMthdAppStd": "지방자치단체 입찰시 낙찰자 결정기준",
            "befBidBbancNo": "R26BK01660000",
        }
        resp = make_mock_response(json_data=make_success_response([item]))

        with patch_get(resp):
            result = await service.get_bid_notice_by_no("R26BK01665863")

        assert result.sucsfbidMthdAppStd == "지방자치단체 입찰시 낙찰자 결정기준"
        assert result.befBidBbancNo == "R26BK01660000"


# ---------------------------------------------------------------------------
# get_bid_a_value
# ---------------------------------------------------------------------------

class TestGetBidAValue:
    @pytest.mark.asyncio
    async def test_success_cnstwk(self, service):
        items = [{"bidNtceNo": "20240209001", "bssamt": "1000000000"}]
        resp = make_mock_response(json_data=make_success_response(items))

        with patch_get(resp) as mock_get:
            result = await service.get_bid_a_value("20240209001", bid_type="cnstwk")
            url = mock_get.call_args[0][0]

        assert result.bssamt == "1000000000"
        assert url == NaraJangterService.CNSTWK_BSSAMT_URL

    @pytest.mark.asyncio
    async def test_success_servc_uses_servc_url(self, service):
        items = [{"bidNtceNo": "20240209002", "bssamt": "500000000"}]
        resp = make_mock_response(json_data=make_success_response(items))

        with patch_get(resp) as mock_get:
            result = await service.get_bid_a_value("20240209002", bid_type="servc")
            url = mock_get.call_args[0][0]

        assert result.bidNtceNo == "20240209002"
        assert url == NaraJangterService.SERVC_BSSAMT_URL

    @pytest.mark.asyncio
    async def test_404_returns_none(self, service):
        resp = make_mock_response(status_code=404)
        with patch_get(resp):
            assert await service.get_bid_a_value("NOTFOUND") is None

    @pytest.mark.asyncio
    async def test_rate_limit_raises_not_silently_none(self, service):
        """한도 소진을 None 으로 삼키면 호출자가 '데이터 없음'과 구분할 수 없다."""
        limited = make_mock_response(status_code=429)
        with patch_get(limited):
            with pytest.raises(RateLimitError):
                await service.get_bid_a_value("RATELIMITED")

    @pytest.mark.asyncio
    async def test_empty_items_returns_none(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp):
            assert await service.get_bid_a_value("EMPTY") is None

    @pytest.mark.asyncio
    async def test_single_dict_item(self, service):
        data = make_success_response({"bidNtceNo": "SINGLE", "bssamt": "100"})
        resp = make_mock_response(json_data=data)
        with patch_get(resp):
            result = await service.get_bid_a_value("SINGLE")
        assert result.bidNtceNo == "SINGLE"


# ---------------------------------------------------------------------------
# 날짜 기준 대량 조회 — 에러를 빈 결과로 삼키지 않아야 한다
# ---------------------------------------------------------------------------

class TestBulkDateFetchersAreStrict:
    """이 계열이 에러를 [] 로 반환하면 동기화 윈도우가 0건으로 완료 마킹되어
    해당 구간 데이터가 영구 누락된다."""

    @pytest.mark.asyncio
    async def test_regions_success(self, service):
        items = [{"bidNtceNo": "B001", "bidNtceOrd": "000", "prtcptPsblRgnNm": "서울"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp):
            result = await service.get_prtcpt_psbl_rgn_by_date("x", "y")
        assert result[0].bidNtceNo == "B001"

    @pytest.mark.asyncio
    async def test_regions_rate_limit_raises(self, service):
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.get_prtcpt_psbl_rgn_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_regions_quota_code_raises(self, service):
        resp = make_mock_response(json_data=make_gateway_error_response("22"))
        with patch_get(resp):
            with pytest.raises(RateLimitError):
                await service.get_prtcpt_psbl_rgn_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_regions_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("02", "DB Error"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_prtcpt_psbl_rgn_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_regions_default_num_of_rows_is_999(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp) as mock_get:
            await service.get_prtcpt_psbl_rgn_by_date("x", "y")
            params = mock_get.call_args[1]["params"]
        assert params["numOfRows"] == 999

    @pytest.mark.asyncio
    async def test_license_success(self, service):
        items = [{"bidNtceNo": "L001", "lcnsLmtNm": "건설업"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp):
            result = await service.get_license_limit_by_date("x", "y")
        assert result[0].bidNtceNo == "L001"

    @pytest.mark.asyncio
    async def test_license_rate_limit_raises(self, service):
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.get_license_limit_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_license_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("07", "범위초과"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_license_limit_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_license_service_error_envelope_raises(self, service):
        resp = make_mock_response(json_data=make_service_error_response("07"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_license_limit_by_date("x", "y")
        assert exc.value.code == "07"


# ---------------------------------------------------------------------------
# get_prtcpt_psbl_rgn_by_bid
# ---------------------------------------------------------------------------

class TestGetPrtcptPsblRgnByBid:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [{"bidNtceNo": "B001", "bidNtceOrd": "000", "prtcptPsblRgnNm": "경기"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp) as mock_get:
            result = await service.get_prtcpt_psbl_rgn_by_bid("B001")
            params = mock_get.call_args[1]["params"]

        assert result[0].prtcptPsblRgnNm == "경기"
        # 부속 데이터 엔드포인트는 inqryDiv=2 + bidNtceNo 필터가 정상 동작한다.
        assert params["inqryDiv"] == 2
        assert params["bidNtceNo"] == "B001"

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, service):
        with patch_get(make_mock_response(status_code=404)):
            assert await service.get_prtcpt_psbl_rgn_by_bid("NOTFOUND") == []

    @pytest.mark.asyncio
    async def test_rate_limit_raises(self, service):
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.get_prtcpt_psbl_rgn_by_bid("X")


# ---------------------------------------------------------------------------
# get_bid_opening_results
# ---------------------------------------------------------------------------

class TestGetBidOpeningResults:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [{"bidNtceNo": "R001", "opengRank": "1", "prcbdrNm": "회사"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp):
            result = await service.get_bid_opening_results("R001")
        assert result[0].prcbdrNm == "회사"

    @pytest.mark.asyncio
    async def test_num_of_rows_passed_through(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp) as mock_get:
            await service.get_bid_opening_results("X", numOfRows=50)
            params = mock_get.call_args[1]["params"]
        assert params["numOfRows"] == 50


# ---------------------------------------------------------------------------
# search_bids
# ---------------------------------------------------------------------------

class TestSearchBids:
    def _params(self, **kw):
        base = dict(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            numOfRows=100,
            pageNo=1,
        )
        base.update(kw)
        return BidSearchParams(**base)

    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [
            {
                "bidNtceNo": "R26BK01665863",
                "bidNtceOrd": "000",
                "bidNtceNm": "공고",
                "ntceInsttNm": "기관",
            }
        ]
        resp = make_mock_response(json_data=make_success_response(items, 1))
        with patch_get(resp):
            result = await service.search_bids("contract", self._params())

        assert result.totalCount == 1
        assert result.items[0].bidNtceNo == "R26BK01665863"

    @pytest.mark.asyncio
    async def test_uses_ppssrch_endpoint(self, service):
        resp = make_mock_response(json_data=make_success_response([], 0))
        with patch_get(resp) as mock_get:
            await service.search_bids("contract", self._params())
            url = mock_get.call_args[0][0]
        assert url == NaraJangterService.BASE_CNST_URL

    @pytest.mark.asyncio
    async def test_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("01", "App Error"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.search_bids("contract", self._params())

    @pytest.mark.asyncio
    async def test_rate_limit_raises(self, service):
        """공고 조회도 한도 소진 시 RateLimitError 여야 한다.

        기존 구현은 여기에 키 로테이션이 없어, V1 한도가 끝나면 V2~V4 가
        남아 있어도 공고 수집 전체가 죽었다.
        """
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.search_bids("contract", self._params())

    @pytest.mark.asyncio
    async def test_rate_limit_rotates_key(self, multikey_service):
        limited = make_mock_response(status_code=429)
        ok = make_mock_response(json_data=make_success_response([], 0))
        with patch_get(limited, ok):
            await multikey_service.search_bids("contract", self._params())
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, service):
        resp = make_mock_response(json_raises=True, text="boom")
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.search_bids("contract", self._params())

    @pytest.mark.asyncio
    async def test_optional_filters_passed(self, service):
        resp = make_mock_response(json_data=make_success_response([], 0))
        params = self._params(prtcptLmtRgnNm="경기도", indstrytyNm="조경식재")
        with patch_get(resp) as mock_get:
            await service.search_bids("contract", params)
            q = mock_get.call_args[1]["params"]
        assert q["prtcptLmtRgnNm"] == "경기도"
        assert q["indstrytyNm"] == "조경식재"

    @pytest.mark.asyncio
    async def test_no_data_returns_empty_response(self, service):
        resp = make_mock_response(json_data=make_error_response("03", "NODATA"))
        with patch_get(resp):
            result = await service.search_bids("contract", self._params())
        assert result.items == []
        assert result.totalCount == 0


# ---------------------------------------------------------------------------
# 02 API 전환: URL 상수
# ---------------------------------------------------------------------------

BASE_02 = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService02/"

BID_NOTICE_URL_NAMES = [
    "BASE_CNST_URL", "BASE_SERV_URL", "PLAIN_CNST_URL", "PLAIN_SERV_URL",
    "CNSTWK_BSSAMT_URL", "SERVC_BSSAMT_URL", "PRTCPT_PSBL_RGN_URL",
    "LICENSE_LIMIT_URL", "ATCH_FILE_URL", "EORDER_ATCH_FILE_URL",
    "INCNTV_RGN_URL", "JNTCONTRCT_DUTY_RGN_URL", "SUBSI_CNSTTY_URL",
]


class TestVersion02Urls:
    @pytest.mark.parametrize("name", BID_NOTICE_URL_NAMES)
    def test_bid_notice_urls_use_02_base_https(self, name):
        url = getattr(NaraJangterService, name)
        assert url.startswith(BASE_02)
        assert url.endswith("02")

    def test_url_dict_points_to_02(self):
        assert NaraJangterService.url_dict["contract"].endswith("CnstwkPPSSrch02")
        assert NaraJangterService.url_dict["service"].endswith("ServcPPSSrch02")

    def test_scsbid_urls_unchanged(self):
        base = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/"
        assert NaraJangterService.OPENG_RESULT_URL == (
            base + "getOpengResultListInfoOpengCompt"
        )
        assert NaraJangterService.CNSTWK_RESERVE_PRICE_URL == (
            base + "getOpengResultListInfoCnstwkPreparPcDetail"
        )
        assert NaraJangterService.SERVC_RESERVE_PRICE_URL == (
            base + "getOpengResultListInfoServcPreparPcDetail"
        )

    def test_new_endpoint_names(self):
        assert NaraJangterService.ATCH_FILE_URL.endswith(
            "getBidPblancListInfoAtchFileInfo02")
        assert NaraJangterService.EORDER_ATCH_FILE_URL.endswith(
            "getBidPblancListInfoEorderAtchFileInfo02")
        assert NaraJangterService.INCNTV_RGN_URL.endswith(
            "getBidPblancIncntvRgnListInfo02")
        assert NaraJangterService.JNTCONTRCT_DUTY_RGN_URL.endswith(
            "getBidPblancJntcontrctDutyRgnListInfo02")
        assert NaraJangterService.SUBSI_CNSTTY_URL.endswith(
            "getBidPblancSubsiCnsttyIndstrytyListInfo02")


class TestBsnsDivCd:
    @pytest.mark.parametrize(
        "bid_type,expected",
        [("cnstwk", "3"), ("servc", "5"), ("service", "5"), ("용역", "5"),
         (None, "3"), ("", "3")],
    )
    def test_mapping(self, bid_type, expected):
        assert NaraJangterService.bsns_div_cd(bid_type) == expected


# ---------------------------------------------------------------------------
# 02 API 전환: 신규 조회 메서드
# ---------------------------------------------------------------------------

class TestGetAttachmentsByBid:
    @pytest.mark.asyncio
    async def test_cnstwk_params_and_parse(self, service):
        items = [{
            "bidNtceNo": "B1", "bidNtceOrd": "001", "atchSno": "1",
            "atchDocDivNm": "공고서", "atchFileNm": "공고문.pdf",
            "atchFileUrl": "https://www.g2b.go.kr/x",
        }]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp) as mock_get:
            result = await service.get_attachments_by_bid("B1", "001")
            url = mock_get.call_args[0][0]
            params = mock_get.call_args[1]["params"]

        assert url == NaraJangterService.ATCH_FILE_URL
        assert params["inqryDiv"] == 2
        assert params["bidNtceNo"] == "B1"
        assert params["bidNtceOrd"] == "001"
        assert params["bsnsDivCd"] == "3"
        assert params["numOfRows"] == NaraJangterService.MAX_PAGE_SIZE
        assert params["type"] == "json"
        assert result[0].atchFileNm == "공고문.pdf"
        assert result[0].atchFileUrl == "https://www.g2b.go.kr/x"

    @pytest.mark.asyncio
    async def test_servc_uses_div_5(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp) as mock_get:
            await service.get_attachments_by_bid("B1", bid_type="servc")
            params = mock_get.call_args[1]["params"]
        assert params["bsnsDivCd"] == "5"
        assert params["bidNtceOrd"] == "000"

    @pytest.mark.asyncio
    async def test_single_dict_item(self, service):
        item = {"bidNtceNo": "B1", "bidNtceOrd": "000", "atchFileNm": "a.hwp"}
        resp = make_mock_response(json_data=make_success_response(item))
        with patch_get(resp):
            result = await service.get_attachments_by_bid("B1")
        assert len(result) == 1 and result[0].atchFileNm == "a.hwp"

    @pytest.mark.asyncio
    async def test_no_data_returns_empty(self, service):
        resp = make_mock_response(json_data=make_error_response("03", "NO DATA"))
        with patch_get(resp):
            assert await service.get_attachments_by_bid("B1") == []

    @pytest.mark.asyncio
    async def test_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("99", "boom"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_attachments_by_bid("B1")


class TestGetEorderAttachmentsByBid:
    @pytest.mark.asyncio
    async def test_params_and_parse(self, service):
        items = [{
            "bidNtceNo": "B1", "bidNtceOrd": "000", "atchSno": "1",
            "eorderDocDivNm": "제안요청서", "eorderAtchFileNm": "rfp.pdf",
            "eorderAtchFileUrl": "https://e/rfp",
        }]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp) as mock_get:
            result = await service.get_eorder_attachments_by_bid("B1")
            url = mock_get.call_args[0][0]
            params = mock_get.call_args[1]["params"]

        assert url == NaraJangterService.EORDER_ATCH_FILE_URL
        assert params["inqryDiv"] == 2
        assert params["bidNtceNo"] == "B1"
        assert params["bidNtceOrd"] == "000"
        assert "bsnsDivCd" not in params
        assert result[0].eorderDocDivNm == "제안요청서"
        assert result[0].eorderAtchFileUrl == "https://e/rfp"

    @pytest.mark.asyncio
    async def test_single_dict_and_no_data(self, service):
        item = {"bidNtceNo": "B1", "eorderAtchFileNm": "x"}
        with patch_get(make_mock_response(json_data=make_success_response(item))):
            assert len(await service.get_eorder_attachments_by_bid("B1")) == 1
        with patch_get(make_mock_response(json_data=make_error_response("03", "n"))):
            assert await service.get_eorder_attachments_by_bid("B1") == []

    @pytest.mark.asyncio
    async def test_error_raises(self, service):
        with patch_get(make_mock_response(json_data=make_error_response("99", "e"))):
            with pytest.raises(NaraJangterApiError):
                await service.get_eorder_attachments_by_bid("B1")


class TestSubDatasetByDateFetchers:
    CASES = [
        ("get_incntv_rgn_by_date", "INCNTV_RGN_URL",
         {"bidNtceNo": "B1", "bidNtceOrd": "000", "sno": "1",
          "IncntvRgnNm": "부산광역시"},
         "incntvRgnNm", "부산광역시"),
        ("get_jntcontrct_duty_rgn_by_date", "JNTCONTRCT_DUTY_RGN_URL",
         {"bidNtceNo": "B1", "bidNtceOrd": "000", "sno": "1",
          "rgnDutyJntcontrctRt": "49", "JntcontrctDutyRgnNm": "서울특별시"},
         "jntcontrctDutyRgnNm", "서울특별시"),
        ("get_subsi_cnstty_by_date", "SUBSI_CNSTTY_URL",
         {"bidNtceNo": "B1", "bidNtceOrd": "000", "sno": "1",
          "subsiCnsttyCd": "4992", "subsiCnsttyNm": "도장",
          "subsiCnsttyIndstrytyEvlRt": "47"},
         "subsiCnsttyNm", "도장"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,url_name,item,attr,expected", CASES)
    async def test_params_and_parse(self, service, method, url_name, item, attr, expected):
        resp = make_mock_response(json_data=make_success_response([item]))
        with patch_get(resp) as mock_get:
            result = await getattr(service, method)(
                "202601010000", "202601012359", pageNo=2, numOfRows=50
            )
            url = mock_get.call_args[0][0]
            params = mock_get.call_args[1]["params"]

        assert url == getattr(NaraJangterService, url_name)
        assert params["inqryDiv"] == 1
        assert params["inqryBgnDt"] == "202601010000"
        assert params["inqryEndDt"] == "202601012359"
        assert params["pageNo"] == 2
        assert params["numOfRows"] == 50
        assert params["type"] == "json"
        assert getattr(result[0], attr) == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,url_name,item,attr,expected", CASES)
    async def test_single_dict_item(self, service, method, url_name, item, attr, expected):
        resp = make_mock_response(json_data=make_success_response(item))
        with patch_get(resp) as mock_get:
            result = await getattr(service, method)("a", "b")
            params = mock_get.call_args[1]["params"]
        assert len(result) == 1 and getattr(result[0], attr) == expected
        assert params["pageNo"] == 1
        assert params["numOfRows"] == NaraJangterService.MAX_PAGE_SIZE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,url_name,item,attr,expected", CASES)
    async def test_no_data_returns_empty(self, service, method, url_name, item, attr, expected):
        resp = make_mock_response(json_data=make_error_response("03", "NO DATA"))
        with patch_get(resp):
            assert await getattr(service, method)("a", "b") == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,url_name,item,attr,expected", CASES)
    async def test_errors_propagate(self, service, method, url_name, item, attr, expected):
        with patch_get(make_mock_response(json_data=make_error_response("99", "e"))):
            with pytest.raises(NaraJangterApiError):
                await getattr(service, method)("a", "b")
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await getattr(service, method)("a", "b")
