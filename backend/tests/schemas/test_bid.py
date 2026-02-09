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
