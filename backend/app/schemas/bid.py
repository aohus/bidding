from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BidSearchParams(BaseModel):
    inqryDiv: str = "1"  # 1:공고게시일시, 2:개찰일시
    inqryBgnDt: str  # YYYYMMDDHHMM
    inqryEndDt: str  # YYYYMMDDHHMM
    prtcptLmtRgnNm: Optional[str] = None # 입찰참가제한지역명
    indstrytyNm: Optional[str] = None # 업종명
    presmptPrceBgn: Optional[str] = None # 추정가격범위시작
    presmptPrceEnd: Optional[str] = None  # 추정가격범위끝
    bidClseExcpYn: Optional[str] = None  # Y or N
    numOfRows: int = 100
    pageNo: int = 1


class BidItem(BaseModel):
    bidNtceNo: str
    bidNtceOrd: str
    bidNtceNm: str
    ntceInsttNm: str
    dminsttNm: Optional[str] = None # 수요기관명
    bidMethdNm: Optional[str] = None # 입찰방법명
    mainCnsttyNm: Optional[str] = None # 주공종명
    cntrctCnclsMthdNm: Optional[str] = None # 계약체결방법명
    bidBeginDt: Optional[str] = None # 입찰시작일시
    bidClseDt: Optional[str] = None # 입찰마감일시
    opengDt: Optional[str] = None # 개찰일시
    bdgtAmt: Optional[str] = None # 예산금액
    presmptPrce: Optional[str] = None # 추정가격
    bidPrtcptLmtYn: Optional[str] = None # 입찰참가제한여부
    prearngPrceDcsnMthdNm: Optional[str] = None # 예정가격결정방법명
    dsgntCmptYn: Optional[str] = None # 지명경쟁여부
    arsltCmptYn: Optional[str] = None # 실적경쟁여부
    rgnDutyJntcontrctYn: Optional[str] = None # 지역의무공동도급여부 
    sucsfbidLwltRate: Optional[str] = None # 낙찰하한율
    sucsfbidMthdNm: Optional[str] = None # 낙찰방법명
    rgstDt: Optional[str] = None # 등록일시
    bidNtceUrl: Optional[str] = None # 입찰공고URL
    bidNtceDtlUrl: Optional[str] = None # 입찰공고상세URL
    ntceSpecDocUrl1: Optional[str] = None # 공고문서URL1
    ntceSpecDocUrl2: Optional[str] = None
    ntceSpecDocUrl3: Optional[str] = None
    ntceSpecDocUrl4: Optional[str] = None
    ntceSpecDocUrl5: Optional[str] = None
    ntceSpecFileNm1: Optional[str] = None
    ntceSpecFileNm2: Optional[str] = None
    ntceSpecFileNm3: Optional[str] = None
    ntceSpecFileNm4: Optional[str] = None
    ntceSpecFileNm5: Optional[str] = None
    sptDscrptDocUrl1: Optional[str] = None # 지원설명문서URL1
    sptDscrptDocUrl2: Optional[str] = None
    sptDscrptDocUrl3: Optional[str] = None
    sptDscrptFileNm1: Optional[str] = None
    sptDscrptFileNm2: Optional[str] = None
    sptDscrptFileNm3: Optional[str] = None
    stdNtceDocUrl: Optional[str] = None # 표준공고문서URL
    stdNtceDocFileNm: Optional[str] = None # 표준공고문서파일명
    cnstrtsiteRgnNm: Optional[str] = None
    cmmnSpldmdCorpYn: Optional[str] = None
    indstrytyLmtYn: Optional[str] = None
    indstrytyMfrcFldEvlYn: Optional[str] = None # 업종 주력분야 평가 대상 여부
    rgnLmtBidLocplcJdgmBssCd: Optional[str] = None # 지역제한입찰소재지판단기준코드
    rgnLmtBidLocplcJdgmBssNm: Optional[str] = None # 지역제한입찰소재지판단기준명


class BidApiResponse(BaseModel):
    items: List[BidItem]
    totalCount: int
    numOfRows: int
    pageNo: int


class BidAValueItem(BaseModel):
    bidNtceNo: str        # 입찰공고번호
    bidNtceOrd: Optional[str] = None # 입찰공고차수
    bidNtceNm: Optional[str] = None # 입찰공고명
    bssamt: Optional[str] = None # 기초금액
    basePrceAamt: Optional[str] = None     # 기초금액 A값 (Deprecated or keep for compatibility if needed, but spec emphasizes bssamt)
    sftyMngcst: Optional[str] = None       # 산업안전보건관리비
    sftyChckMngcst: Optional[str] = None   # 안전관리비
    rtrfundNon: Optional[str] = None       # 퇴직공제부금비
    mrfnHealthInsrprm: Optional[str] = None # 국민건강보험료
    npnInsrprm: Optional[str] = None       # 국민연금보험료
    odsnLngtrmrcprInsrprm: Optional[str] = None # 노인장기요양보험료
    qltyMngcst: Optional[str] = None      # 품질관리비
    qltyMngcstAObjYn: Optional[str] = None # 품질관리비A적용대상여부
    envCnsrvcst: Optional[str] = None      # 환경보전비
    lbrcstBssRate: Optional[str] = None    # 노무비기준율
    rmrk1: Optional[str] = None            # 비고1
    rmrk2: Optional[str] = None            # 비고2
    inptDt: Optional[str] = None           # 입력일시
    rsrvtnPrceRngBgnRate: Optional[str] = None # 예비가격범위시작률
    rsrvtnPrceRngEndRate: Optional[str] = None # 예비가격범위종료율
    etcGnrlexpnsBssRate: Optional[str] = None # 기타경비기준율
    usefulAmt: Optional[str] = None        # 가용금액
    resultCode: Optional[str] = None       # 결과코드
    bssamtOpenDt: Optional[str] = None     # 기초금액공개일시
    evlBssAmt: Optional[str] = None        # 평가기준금액
    gnrlMngcstBssRate: Optional[str] = None # 일반관리비기준율
    scontrctPayprcePayGrntyFee: Optional[str] = None # 하도급대금지급보증수수료
    dfcltydgrCfcnt: Optional[str] = None   # 난이도계수
    prftBssRate: Optional[str] = None      # 이윤기준율
    bidClsfcNo: Optional[str] = None       # 입찰분류번호
    bidPrceCalclAValYn: Optional[str] = None # 입찰가격산식A여부
    bssAmtPurcnstcst: Optional[str] = None # 기초금액순공사비
    smkpAmt: Optional[str] = None          # 표준시장단가금액 (원화,원)
    smkpAmtYn: Optional[str] = None        # 표준시장단가금액A적용대상여부
