from app.schemas.bid import BidAValueItem
import pytest
from pydantic import ValidationError

def test_bid_avalue_item_fields():
    """
    Test that BidAValueItem model includes the new required 'bssamt' field
    and other mapped fields.
    """
    # This data represents the new expected structure with all fields from the spec
    data = {
        "bidNtceNo": "20240209001",
        "bssamt": "1000000000",
        "envCnsrvcst": "500000",
        "mrfnHealthInsrprm": "100000",
        "odsnLngtrmrcprInsrprm": "50000",
        "sftyMngcst": "300000",
        "lbrcstBssRate": "15.5",
        "evlBssAmt": "950000000",
        "resultCode": "00",
        "scontrctPayprcePayGrntyFee": "1000",
        "dfcltydgrCfcnt": "1.0",
        "prftBssRate": "5.0",
        "bidClsfcNo": "1",
        "bidPrceCalclAValYn": "Y",
        "bssAmtPurcnstcst": "900000000"
    }

    # This should fail if fields are missing or extra fields are not allowed (default is ignore usually, 
    # but we want to access them, so if they are not defined in schema, accessing item.bssamt will fail)
    item = BidAValueItem(**data)
    
    assert item.bidNtceNo == "20240209001"
    assert item.bssamt == "1000000000"
    assert item.envCnsrvcst == "500000"
    assert item.mrfnHealthInsrprm == "100000"
    assert item.sftyMngcst == "300000"


# ---------------------------------------------------------------------------
# 02 API 전환: 신규 스키마
# ---------------------------------------------------------------------------

from app.schemas.bid import (  # noqa: E402
    BidAttachment,
    BidAttachmentItem,
    BidAttachmentsResponse,
    BidEorderAttachmentItem,
    BidItem,
    BidSearchParams,
    IncntvRgnItem,
    JntcontrctDutyRgnItem,
    SubsiCnsttyInfo,
    SubsiCnsttyItem,
)


def test_incntv_rgn_item_accepts_capitalized_alias():
    item = IncntvRgnItem(
        **{"bidNtceNo": "N1", "bidNtceOrd": "000", "sno": "1", "IncntvRgnNm": "부산광역시"}
    )
    assert item.incntvRgnNm == "부산광역시"


def test_incntv_rgn_item_accepts_field_name():
    item = IncntvRgnItem(bidNtceNo="N1", bidNtceOrd="000", incntvRgnNm="부산광역시")
    assert item.incntvRgnNm == "부산광역시"


def test_jntcontrct_duty_rgn_item_alias_and_field_name():
    by_alias = JntcontrctDutyRgnItem(
        **{
            "bidNtceNo": "N1", "bidNtceOrd": "000", "rgnDutyJntcontrctRt": "49",
            "JntcontrctDutyRgnNm": "서울특별시",
        }
    )
    by_name = JntcontrctDutyRgnItem(
        bidNtceNo="N1", bidNtceOrd="000", jntcontrctDutyRgnNm="서울특별시"
    )
    assert by_alias.jntcontrctDutyRgnNm == "서울특별시"
    assert by_alias.rgnDutyJntcontrctRt == "49"
    assert by_name.jntcontrctDutyRgnNm == "서울특별시"


def test_subsi_cnstty_item_parses_all_fields():
    item = SubsiCnsttyItem(
        bidNtceNo="N1", bidNtceOrd="000", sno="1", subsiCnsttyCd="4992",
        subsiCnsttyNm="도장ㆍ습식ㆍ방수ㆍ석공사업", subsiCnsttyIndstrytyEvlRt="47",
    )
    assert item.subsiCnsttyCd == "4992"
    assert item.subsiCnsttyIndstrytyEvlRt == "47"


def test_attachment_items_require_bid_no():
    with pytest.raises(ValidationError):
        BidAttachmentItem(bidNtceOrd="000")
    with pytest.raises(ValidationError):
        BidEorderAttachmentItem()
    item = BidEorderAttachmentItem(bidNtceNo="N1", eorderAtchFileUrl="https://x")
    assert item.bidNtceOrd is None


def test_bid_attachment_source_literal_enforced():
    ok = BidAttachment(source="legacy", fileNm="a.pdf", fileUrl="https://x")
    assert ok.docDivNm is None and ok.sno is None
    with pytest.raises(ValidationError):
        BidAttachment(source="other", fileNm="a.pdf", fileUrl="https://x")


def test_bid_attachments_response_wraps_items():
    resp = BidAttachmentsResponse(
        bidNtceNo="N1", bidNtceOrd="000",
        items=[BidAttachment(source="ntce", fileNm="a.pdf", fileUrl="u", sno=1)],
    )
    assert resp.items[0].sno == 1


def test_bid_item_new_fields_default_none():
    item = BidItem(bidNtceNo="N1", bidNtceOrd="000", bidNtceNm="n", ntceInsttNm="i")
    for name in (
        "incntvRgnNms", "jntcontrctDutyRgnNms", "rgnDutyJntcontrctRt",
        "subsiCnsttys", "isIncntvRgnMatch", "isJntcontrctDutyRgnMatch",
    ):
        assert getattr(item, name) is None


def test_bid_item_accepts_subsi_info_list():
    item = BidItem(
        bidNtceNo="N1", bidNtceOrd="000", bidNtceNm="n", ntceInsttNm="i",
        subsiCnsttys=[SubsiCnsttyInfo(nm="도장", evlRt="47")],
        isIncntvRgnMatch=True,
    )
    assert item.subsiCnsttys[0].nm == "도장"
    assert item.isIncntvRgnMatch is True


def test_bid_search_params_new_flags_default_none():
    p = BidSearchParams(inqryBgnDt="202601010000", inqryEndDt="202601020000")
    assert p.incntvRgnOnly is None
    assert p.jntcontrctDutyRgnOnly is None
    assert p.includeSubsiCnstty is None
    p2 = BidSearchParams(
        inqryBgnDt="a", inqryEndDt="b", incntvRgnOnly=True,
        jntcontrctDutyRgnOnly=False, includeSubsiCnstty=True,
    )
    assert p2.incntvRgnOnly is True and p2.jntcontrctDutyRgnOnly is False
