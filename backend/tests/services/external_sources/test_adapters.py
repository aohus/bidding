"""어댑터 필드 매핑 테스트 — 전부 실제 API 응답 픽스처 기반.

문서와 실제 응답이 어긋나는 지점(BCode 대소문자, LH 의 items 래퍼 부재,
EUC-KR, '-' sentinel 등)이 여기서 고정된다.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.external_sources.base import ExternalApiError
from app.services.external_sources.kdhc import KdhcSource
from app.services.external_sources.kepco import KepcoSource
from app.services.external_sources.kogas import KogasSource
from app.services.external_sources.kra import KraSource
from app.services.external_sources.kwater import KwaterSource
from app.services.external_sources.lh import LhSource
from app.services.external_sources.registry import (
    SOURCES,
    ExternalBidSource,
    get_source,
    source_ids,
)

from .conftest import load_bytes

DAY_START = "202610120000"
DAY_END = "202610122359"

EMPTY_XML = (
    b'<response><header><resultCode>00</resultCode>'
    b'<resultMsg>NORMAL SERVICE.</resultMsg></header>'
    b'<body><items/><totalCount>0</totalCount></body></response>'
)


def xml_response(body: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = body
    resp.text = body.decode("utf-8", "replace")
    return resp


def patch_xml(*bodies):
    """순차 XML 응답으로 httpx GET 을 패치합니다.

    마지막 응답은 소진 후에도 계속 반환된다 — 어댑터가 호출 횟수를 바꿔도
    테스트가 깨지지 않게 하기 위함 (호출 횟수 자체를 검증하는 테스트는
    별도로 side_effect 길이를 고정한다).
    """
    responses = [xml_response(b) for b in bodies]

    async def _get(*args, **kwargs):
        return responses.pop(0) if len(responses) > 1 else responses[0]

    return patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_get))


# ---------------------------------------------------------------------------
# 레지스트리
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_six_sources_registered(self):
        assert set(source_ids()) == {
            "lh", "kwater", "kdhc", "kra", "kogas", "kepco"
        }

    def test_every_source_satisfies_protocol(self):
        for src in SOURCES.values():
            assert isinstance(src, ExternalBidSource)

    def test_source_id_matches_dict_key(self):
        for key, src in SOURCES.items():
            assert src.source == key

    def test_granularity_is_known_value(self):
        for src in SOURCES.values():
            assert src.granularity in ("day", "month")

    def test_kwater_is_month_granularity(self):
        """searchDt 가 YYYYMM 이라 일별 윈도우로는 같은 달을 매일 재조회한다."""
        assert SOURCES["kwater"].granularity == "month"

    def test_unknown_source_raises(self):
        with pytest.raises(KeyError, match="unknown external source"):
            get_source("nope")


# ---------------------------------------------------------------------------
# 지역난방공사
# ---------------------------------------------------------------------------

class TestKdhc:
    @pytest.mark.asyncio
    async def test_maps_notice_fields(self):
        with patch_xml(load_bytes("kdhc_notices.xml"), EMPTY_XML):
            fetched = await KdhcSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.source == "kdhc"
        assert notice.notice_no
        assert notice.title
        assert notice.work_div in ("용역", "구매", "공사", "물품")
        assert notice.rgst_dt and len(notice.rgst_dt) == 12
        assert notice.openg_dt and len(notice.openg_dt) == 12
        assert notice.status

    @pytest.mark.asyncio
    async def test_uses_date_range_params(self):
        with patch_xml(EMPTY_XML) as mock_get:
            await KdhcSource().fetch(DAY_START, DAY_END)

        params = mock_get.call_args.kwargs["params"]
        assert params["startDate"] == "20261012"
        assert params["endDate"] == "20261012"

    @pytest.mark.asyncio
    async def test_produces_no_results_records(self):
        """지역난방 API 는 낙찰 상세를 주지 않는다."""
        with patch_xml(load_bytes("kdhc_notices.xml"), EMPTY_XML):
            fetched = await KdhcSource().fetch(DAY_START, DAY_END)

        assert fetched.results == ()


# ---------------------------------------------------------------------------
# 토지주택공사 (EUC-KR, items 래퍼 없음)
# ---------------------------------------------------------------------------

class TestLh:
    @pytest.mark.asyncio
    async def test_maps_notice_fields_from_euckr_response(self):
        with patch_xml(load_bytes("lh_notices.xml"), EMPTY_XML):
            fetched = await LhSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.source == "lh"
        assert notice.notice_no == "2603536"
        assert notice.notice_ord == "00"
        # EUC-KR 디코딩이 깨지면 치환문자가 섞인다.
        assert notice.title and "�" not in notice.title
        assert notice.institution == "부산울산지역본부"
        assert notice.cntrct_mthd == "수의공고"
        assert notice.status == "마감"

    @pytest.mark.asyncio
    async def test_parses_slash_separated_datetimes(self):
        """LH 는 '2026/10/08 15:00' 형식을 쓴다."""
        with patch_xml(load_bytes("lh_notices.xml"), EMPTY_XML):
            fetched = await LhSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.bid_close_dt == "202610081500"
        assert notice.openg_dt == "202610081600"

    @pytest.mark.asyncio
    async def test_parses_presumed_price(self):
        with patch_xml(load_bytes("lh_notices.xml"), EMPTY_XML):
            fetched = await LhSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].presmpt_prce == 30316615

    @pytest.mark.asyncio
    async def test_preserves_full_raw_payload(self):
        """지역제한/면허 필드는 정규화 컬럼에 없으므로 data 에 남아야 한다."""
        with patch_xml(load_bytes("lh_notices.xml"), EMPTY_XML):
            fetched = await LhSource().fetch(DAY_START, DAY_END)

        raw = fetched.notices[0].data
        assert "zoneRstrct1" in raw
        assert "req1Reqlic1Nm" in raw
        # JSONB 로 저장되므로 직렬화 가능해야 한다.
        json.dumps(raw)

    @pytest.mark.asyncio
    async def test_uses_tndrbid_reg_dt_params(self):
        with patch_xml(EMPTY_XML) as mock_get:
            await LhSource().fetch(DAY_START, DAY_END)

        params = mock_get.call_args.kwargs["params"]
        assert params["tndrbidRegDtStart"] == "20261012"
        assert params["tndrbidRegDtEnd"] == "20261012"


# ---------------------------------------------------------------------------
# 가스공사 (대문자 필드, 공고+낙찰 동일 행)
# ---------------------------------------------------------------------------

class TestKogas:
    @pytest.mark.asyncio
    async def test_maps_uppercase_fields(self):
        with patch_xml(load_bytes("kogas_notices.xml"), EMPTY_XML):
            fetched = await KogasSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.source == "kogas"
        assert notice.notice_no
        assert notice.title
        assert notice.institution == "한국가스공사"
        assert notice.work_div
        assert notice.cntrct_mthd

    @pytest.mark.asyncio
    async def test_parses_minute_precision_datetimes(self):
        with patch_xml(load_bytes("kogas_notices.xml"), EMPTY_XML):
            fetched = await KogasSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.rgst_dt and notice.rgst_dt.endswith("0000")
        assert notice.bid_close_dt and len(notice.bid_close_dt) == 12
        assert notice.openg_dt and len(notice.openg_dt) == 12

    @pytest.mark.asyncio
    async def test_no_result_record_when_no_winner(self):
        """미낙찰 공고는 SUCCESS_* 가 빈 엘리먼트로 온다."""
        with patch_xml(load_bytes("kogas_notices.xml"), EMPTY_XML):
            fetched = await KogasSource().fetch(DAY_START, DAY_END)

        for result in fetched.results:
            assert result.bidder_nm

    @pytest.mark.asyncio
    async def test_builds_result_record_when_winner_present(self):
        body = (
            b'<response><header><resultCode>00</resultCode>'
            b'<resultMsg>ok</resultMsg></header><body><items><item>'
            b'<NOTICE_CODE>2026101207</NOTICE_CODE>'
            b'<NOTICE_NAME>test</NOTICE_NAME>'
            b'<NOTICE_DT>2026-10-12</NOTICE_DT>'
            b'<OPEN_DT>2026-10-16 10:03</OPEN_DT>'
            b'<SUCCESS_CORP_NAME>abc</SUCCESS_CORP_NAME>'
            b'<SUCCESS_AMT>1,234,000</SUCCESS_AMT>'
            b'<SUCCESS_DT>2026-10-16</SUCCESS_DT>'
            b'</item></items><totalCount>1</totalCount></body></response>'
        )
        with patch_xml(body, EMPTY_XML):
            fetched = await KogasSource().fetch(DAY_START, DAY_END)

        assert len(fetched.results) == 1
        result = fetched.results[0]
        assert result.bidder_nm == "abc"
        assert result.bidder_amt == 1234000
        assert fetched.notices[0].status == "낙찰"

    @pytest.mark.asyncio
    async def test_cancelled_notice_status(self):
        body = (
            b'<response><header><resultCode>00</resultCode>'
            b'<resultMsg>ok</resultMsg></header><body><items><item>'
            b'<NOTICE_CODE>1</NOTICE_CODE><CANCEL_YN>Y</CANCEL_YN>'
            b'</item></items><totalCount>1</totalCount></body></response>'
        )
        with patch_xml(body, EMPTY_XML):
            fetched = await KogasSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].status == "취소"

    @pytest.mark.asyncio
    async def test_uses_docdate_params(self):
        with patch_xml(EMPTY_XML) as mock_get:
            await KogasSource().fetch(DAY_START, DAY_END)

        params = mock_get.call_args.kwargs["params"]
        assert params["DOCDATE_START"] == "20261012"
        assert params["DOCDATE_END"] == "20261012"


# ---------------------------------------------------------------------------
# 마사회 (코드 → 명칭, 날짜 단건 순회)
# ---------------------------------------------------------------------------

class TestKra:
    @pytest.mark.asyncio
    async def test_maps_bcode_uppercase(self):
        """문서는 bCode 지만 실제 응답은 BCode 다."""
        with patch_xml(load_bytes("kra_notices.xml"), EMPTY_XML):
            fetched = await KraSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].notice_no == "2026040700"

    @pytest.mark.asyncio
    async def test_decodes_code_fields_to_names(self):
        with patch_xml(load_bytes("kra_notices.xml"), EMPTY_XML):
            fetched = await KraSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.work_div == "일반용역"      # workType 03
        assert notice.cntrct_mthd == "제한경쟁"    # contMethod 3
        assert notice.status == "완료(유찰)"       # status 98

    @pytest.mark.asyncio
    async def test_combines_split_date_and_time_fields(self):
        with patch_xml(load_bytes("kra_notices.xml"), EMPTY_XML):
            fetched = await KraSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.rgst_dt == "202604251810"       # 20260425 + 18:10
        assert notice.bid_close_dt == "202605071400"  # 20260507 + 14:00
        assert notice.openg_dt == "202605071500"      # 20260507 + 15:00

    @pytest.mark.asyncio
    async def test_unknown_code_keeps_raw_value(self):
        """미등록 코드를 None 으로 떨구면 신규 코드 데이터가 사라진다."""
        body = (
            b'<response><header><resultCode>00</resultCode>'
            b'<resultMsg>ok</resultMsg></header><body><items><item>'
            b'<BCode>1</BCode><workType>77</workType>'
            b'</item></items><totalCount>1</totalCount></body></response>'
        )
        with patch_xml(body, EMPTY_XML):
            fetched = await KraSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].work_div == "77"

    @pytest.mark.asyncio
    async def test_maps_result_records(self):
        with patch_xml(EMPTY_XML, load_bytes("kra_results.xml")):
            fetched = await KraSource().fetch(DAY_START, DAY_END)

        result = fetched.results[0]
        assert result.source == "kra"
        assert result.notice_no
        assert result.status_nm == "완료(낙찰)"
        assert result.openg_dt and len(result.openg_dt) == 12

    @pytest.mark.asyncio
    async def test_queries_each_day_in_window(self):
        """notice_date 는 범위가 아니라 단건이라 하루씩 순회해야 한다."""
        with patch_xml(EMPTY_XML) as mock_get:
            await KraSource().fetch("202610100000", "202610122359")

        sent = [c.kwargs["params"] for c in mock_get.call_args_list]
        notice_days = {p["notice_date"] for p in sent if "notice_date" in p}
        result_days = {p["open_date"] for p in sent if "open_date" in p}
        assert notice_days == {"20261010", "20261011", "20261012"}
        assert result_days == {"20261010", "20261011", "20261012"}


# ---------------------------------------------------------------------------
# 수자원공사 (월 단위, rstList 는 구분코드 필수)
# ---------------------------------------------------------------------------

class TestKwater:
    @pytest.mark.asyncio
    async def test_maps_notice_fields(self):
        with patch_xml(load_bytes("kwater_cntrwk.xml"), EMPTY_XML):
            fetched = await KwaterSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.source == "kwater"
        assert notice.notice_no
        assert notice.work_div == "공사"
        assert notice.institution
        assert notice.rgst_dt and len(notice.rgst_dt) == 12

    @pytest.mark.asyncio
    async def test_price_present_once_bidding_completes(self):
        """참가신청 단계 공고는 tndrPlnprc=0 (예정가격 미공개) → None.

        입찰완료 공고에는 값이 들어온다.
        """
        with patch_xml(load_bytes("kwater_cntrwk.xml"), EMPTY_XML):
            fetched = await KwaterSource().fetch(DAY_START, DAY_END)

        by_status = {n.status: n for n in fetched.notices}
        assert by_status["참가신청"].presmpt_prce is None
        assert by_status["입찰완료"].presmpt_prce == 82704566

    @pytest.mark.asyncio
    async def test_dash_sentinel_becomes_none(self):
        """tndrPblancEnddt 는 값 없을 때 '-' 로 온다."""
        body = (
            b'<response><header><resultCode>00</resultCode>'
            b'<resultMsg>ok</resultMsg></header><body><items><item>'
            b'<tndrPbanno>B1</tndrPbanno><tndrPblancDe>20220531</tndrPblancDe>'
            b'<tndrPblancEnddt>-</tndrPblancEnddt>'
            b'</item></items><totalCount>1</totalCount></body></response>'
        )
        with patch_xml(body, EMPTY_XML):
            fetched = await KwaterSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].bid_close_dt is None

    @pytest.mark.asyncio
    async def test_uses_month_search_param(self):
        with patch_xml(EMPTY_XML) as mock_get:
            await KwaterSource().fetch(DAY_START, DAY_END)

        months = {
            c.kwargs["params"]["searchDt"] for c in mock_get.call_args_list
        }
        assert months == {"202610"}

    @pytest.mark.asyncio
    async def test_result_list_iterates_all_division_codes(self):
        """rstList 는 cntrctDivCd 가 없으면 조용히 0건이 온다 — 1~4 순회 필수."""
        with patch_xml(EMPTY_XML) as mock_get:
            await KwaterSource().fetch(DAY_START, DAY_END)

        divs = {
            c.kwargs["params"].get("cntrctDivCd")
            for c in mock_get.call_args_list
        }
        assert {"1", "2", "3", "4"} <= divs

    @pytest.mark.asyncio
    async def test_notice_lists_do_not_send_division_code(self):
        """cntrwkList/servcList 는 cntrctDivCd 를 무시한다 — 보내지 않는다."""
        with patch_xml(EMPTY_XML) as mock_get:
            await KwaterSource().fetch(DAY_START, DAY_END)

        notice_calls = [
            c for c in mock_get.call_args_list
            if "cntrwkList" in c.args[0] or "servcList" in c.args[0]
        ]
        assert notice_calls
        for call in notice_calls:
            assert "cntrctDivCd" not in call.kwargs["params"]

    @pytest.mark.asyncio
    async def test_result_seq_is_per_notice_not_per_batch(self):
        """같은 공고의 복수 결과가 seq 를 공유하면 PK 충돌로 덮어쓴다."""
        body = (
            b'<response><header><resultCode>00</resultCode>'
            b'<resultMsg>ok</resultMsg></header><body><items>'
            b'<item><tndrPbanno>SAME</tndrPbanno><entrpsNm>A</entrpsNm></item>'
            b'<item><tndrPbanno>SAME</tndrPbanno><entrpsNm>B</entrpsNm></item>'
            b'</items><totalCount>2</totalCount></body></response>'
        )
        # 공고 2회(공사/용역) 빈 응답 → 결과 4회(div 1~4) 중 첫 회만 데이터
        with patch_xml(EMPTY_XML, EMPTY_XML, body, EMPTY_XML):
            fetched = await KwaterSource().fetch(DAY_START, DAY_END)

        same = [r for r in fetched.results if r.notice_no == "SAME"]
        assert len(same) == 2
        assert {r.seq for r in same} == {0, 1}

    @pytest.mark.asyncio
    async def test_parses_comma_separated_award_amount(self):
        body = (
            b'<response><header><resultCode>00</resultCode>'
            b'<resultMsg>ok</resultMsg></header><body><items><item>'
            b'<tndrPbanno>B1</tndrPbanno><entrpsNm>A</entrpsNm>'
            b'<scsbidAmt>37,086,150</scsbidAmt>'
            b'<cardPrcsDt>20220526</cardPrcsDt>'
            b'</item></items><totalCount>1</totalCount></body></response>'
        )
        with patch_xml(EMPTY_XML, EMPTY_XML, body, EMPTY_XML):
            fetched = await KwaterSource().fetch(DAY_START, DAY_END)

        result = next(r for r in fetched.results if r.notice_no == "B1")
        assert result.bidder_amt == 37086150
        assert result.openg_dt == "202205260000"


# ---------------------------------------------------------------------------
# 전력개발포털 (JSON, 전용 키)
# ---------------------------------------------------------------------------

def json_response(payload, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = json.dumps(payload) if isinstance(payload, (dict, list)) else "x"
    return resp


def patch_json(response):
    return patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response
    )


@pytest.fixture
def kepco_key(monkeypatch):
    from app.core import config

    monkeypatch.setattr(
        config.settings, "ELECTRIC_INST_SERVICE_KEY", "k" * 40
    )
    return "k" * 40


class TestKepco:
    @pytest.mark.asyncio
    async def test_maps_notice_fields(self, kepco_key):
        payload = json.loads(
            load_bytes("kepco_contract.json").decode("utf-8")
        )
        with patch_json(json_response(payload)):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.source == "kepco"
        assert notice.notice_no
        assert notice.title
        assert notice.institution
        assert notice.rgst_dt and len(notice.rgst_dt) == 12
        # 픽스처의 두 건 모두 금액이 잡혀야 한다 (하나는 추정가격,
        # 하나는 추정금액 폴백 경로).
        assert all(n.presmpt_prce for n in fetched.notices)

    @pytest.mark.asyncio
    async def test_falls_back_to_presumed_amount_for_construction_service(
        self, kepco_key
    ):
        """공사용역 행은 presumedPrice 가 null 이고 presumedAmount 만 있다 (실측).

        폴백하지 않으면 공사용역 공고의 금액이 전부 유실된다.
        """
        payload = {
            "data": [
                {
                    "no": "E1",
                    "purchaseType": "ConstructionService",
                    "presumedPrice": None,
                    "presumedAmount": 703660060,
                    "noticeDate": "20261001",
                }
            ]
        }
        with patch_json(json_response(payload)):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].presmpt_prce == 703660060

    @pytest.mark.asyncio
    async def test_prefers_presumed_price_when_both_present(self, kepco_key):
        payload = {
            "data": [
                {
                    "no": "G1",
                    "presumedPrice": 100,
                    "presumedAmount": 999,
                    "noticeDate": "20261001",
                }
            ]
        }
        with patch_json(json_response(payload)):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].presmpt_prce == 100

    @pytest.mark.asyncio
    async def test_decodes_enum_fields(self, kepco_key):
        payload = {
            "data": [
                {
                    "no": "G1",
                    "name": "t",
                    "companyId": "COM05",
                    "competitionType": "Limited",
                    "itemType": "Construction",
                    "progressState": "Close",
                    "noticeDate": "20261001",
                }
            ]
        }
        with patch_json(json_response(payload)):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        notice = fetched.notices[0]
        assert notice.cntrct_mthd == "제한경쟁"
        assert notice.work_div == "공사"
        assert notice.status == "마감"
        assert notice.institution == "한국중부발전"

    @pytest.mark.asyncio
    async def test_falls_back_to_purchase_type_for_work_div(self, kepco_key):
        payload = {
            "data": [
                {"no": "G1", "purchaseType": "Product", "noticeDate": "20261001"}
            ]
        }
        with patch_json(json_response(payload)):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].work_div == "자재구매"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "item_type,expected",
        [
            ("Construction", "공사"),
            ("Service", "용역"),
            # 명세에 없지만 실측에서 관측된 값 (76건 중 32건).
            ("Product", "자재구매"),
        ],
    )
    async def test_translates_every_observed_item_type(
        self, kepco_key, item_type, expected
    ):
        payload = {
            "data": [
                {
                    "no": "G1",
                    "itemType": item_type,
                    "purchaseType": "ConstructionService",
                    "noticeDate": "20261001",
                }
            ]
        }
        with patch_json(json_response(payload)):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        assert fetched.notices[0].work_div == expected

    @pytest.mark.asyncio
    async def test_uses_api_key_param_not_service_key(self, kepco_key):
        with patch_json(json_response({"data": []})) as mock_get:
            await KepcoSource().fetch(DAY_START, DAY_END)

        params = mock_get.call_args.kwargs["params"]
        assert params["apiKey"] == kepco_key
        assert "serviceKey" not in params

    @pytest.mark.asyncio
    async def test_omits_company_id_to_cover_all_affiliates(self, kepco_key):
        with patch_json(json_response({"data": []})) as mock_get:
            await KepcoSource().fetch(DAY_START, DAY_END)

        assert "companyId" not in mock_get.call_args.kwargs["params"]

    @pytest.mark.asyncio
    async def test_missing_key_raises_config_error(self, monkeypatch):
        from app.core import config

        monkeypatch.setattr(config.settings, "ELECTRIC_INST_SERVICE_KEY", "")
        with pytest.raises(ExternalApiError) as exc:
            await KepcoSource().fetch(DAY_START, DAY_END)

        assert exc.value.code == "CONFIG"

    @pytest.mark.asyncio
    async def test_window_over_90_days_raises(self, kepco_key):
        """API 가 조용히 자르면 그 구간이 완료 마킹되어 영구 누락된다."""
        with pytest.raises(ExternalApiError) as exc:
            await KepcoSource().fetch("202601010000", "202612312359")

        assert exc.value.code == "WINDOW"

    @pytest.mark.asyncio
    async def test_missing_data_key_raises_instead_of_empty(self, kepco_key):
        with patch_json(json_response({"result": "oops"})):
            with pytest.raises(ExternalApiError) as exc:
                await KepcoSource().fetch(DAY_START, DAY_END)

        assert exc.value.code == "PARSE"

    @pytest.mark.asyncio
    async def test_http_error_raises(self, kepco_key):
        with patch_json(json_response({"data": []}, status_code=500)):
            with pytest.raises(ExternalApiError) as exc:
                await KepcoSource().fetch(DAY_START, DAY_END)

        assert exc.value.code == "500"

    @pytest.mark.asyncio
    async def test_skips_non_dict_rows(self, kepco_key):
        with patch_json(json_response({"data": [{"no": "G1"}, "junk", None]})):
            fetched = await KepcoSource().fetch(DAY_START, DAY_END)

        assert len(fetched.notices) == 1
