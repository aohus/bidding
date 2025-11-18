from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class BidSearchParams(BaseModel):
    inqryDiv: str = "1"  # 1:공고게시일시, 2:개찰일시
    inqryBgnDt: str  # YYYYMMDDHHMM
    inqryEndDt: str  # YYYYMMDDHHMM
    prtcptLmtRgnCd: Optional[str] = None
    presmptPrceBgn: Optional[str] = None
    presmptPrceEnd: Optional[str] = None
    numOfRows: int = 100
    pageNo: int = 1


class BidItem(BaseModel):
    bidNtceNo: str
    bidNtceOrd: str
    bidNtceNm: str
    ntceInsttNm: str
    dminsttNm: Optional[str] = None
    bidMethdNm: Optional[str] = None
    cntrctCnclsMthdNm: Optional[str] = None
    bidBeginDt: Optional[str] = None
    bidClseDt: Optional[str] = None
    opengDt: Optional[str] = None
    bdgtAmt: Optional[str] = None
    presmptPrce: Optional[str] = None
    prearngPrceDcsnMthdNm: Optional[str] = None
    sucsfbidLwltRate: Optional[str] = None
    sucsfbidMthdNm: Optional[str] = None
    rgstDt: Optional[str] = None
    ntceSpecDocUrl1: Optional[str] = None
    ntceSpecDocUrl2: Optional[str] = None
    ntceSpecDocUrl3: Optional[str] = None
    ntceSpecDocUrl4: Optional[str] = None
    ntceSpecDocUrl5: Optional[str] = None
    ntceSpecFileNm1: Optional[str] = None
    ntceSpecFileNm2: Optional[str] = None
    ntceSpecFileNm3: Optional[str] = None
    ntceSpecFileNm4: Optional[str] = None
    ntceSpecFileNm5: Optional[str] = None
    sptDscrptDocUrl1: Optional[str] = None
    sptDscrptDocUrl2: Optional[str] = None
    sptDscrptDocUrl3: Optional[str] = None
    sptDscrptFileNm1: Optional[str] = None
    sptDscrptFileNm2: Optional[str] = None
    sptDscrptFileNm3: Optional[str] = None
    stdNtceDocUrl: Optional[str] = None
    stdNtceDocFileNm: Optional[str] = None
    bidNtceUrl: Optional[str] = None
    bidNtceDtlUrl: Optional[str] = None
    cnstrtsiteRgnNm: Optional[str] = None
    cmmnSpldmdCorpYn: Optional[str] = None
    indutyLmtYn: Optional[str] = None


class BidApiResponse(BaseModel):
    items: List[BidItem]
    totalCount: int
    numOfRows: int
    pageNo: int