// API Response
export interface BidApiResponse {
  response: {
    header: {
      resultCode: string;
      resultMsg: string;
    };
    body: {
      items?: BidItem[];
      numOfRows: number;
      pageNo: number;
      totalCount: number;
    };
  };
}

export interface BidAValueApiResponse {
  response: {
    header: {
      resultCode: string;
      resultMsg: string;
    };
    body: {
      items: BidAValueItem[];
      totalCount: number;
    };
  };
}


export interface BidSearchParams {
  inqryDiv: '1' | '2'; // 1:공고게시일시, 2:개찰일시
  inqryBgnDt: string; // YYYYMMDDHHMM
  inqryEndDt: string; // YYYYMMDDHHMM
  prtcptLmtRgnNm?: string; // 참가제한지역명
  cnstrtsiteRgnNm?: string; // 공사현장지역명
  indstrytyNm?: string; // 업종명
  presmptPrceBgn?: string; // 추정가격시작
  presmptPrceEnd?: string; // 추정가격종료
  bidClseExcpYn?: 'Y' | 'N'; // 입찰마감제외여부
  useLocationFilter?: boolean; // 소재지 기준 참가가능지역 필터링
  orderBy?: string; // 정렬 컬럼
  orderDir?: 'asc' | 'desc'; // 정렬 방향
  numOfRows?: number;
  pageNo?: number;
  ServiceKey?: string; // Optional now, managed by backend
}

export interface BidItem {
  bidNtceNo: string; // 입찰공고번호
  bidNtceOrd: string; // 입찰공고차수
  bidNtceNm: string; // 입찰공고명
  ntceInsttNm: string; // 공고기관명
  dminsttNm: string; // 수요기관명
  bidMethdNm: string; // 입찰방식명
  cntrctCnclsMthdNm: string; // 계약체결방법명
  bidBeginDt: string; // 입찰개시일시
  bidClseDt: string; // 입찰마감일시
  opengDt: string; // 개찰일시
  bdgtAmt: string; // 예산금액
  presmptPrce: string; // 추정가격
  prearngPrceDcsnMthdNm: string; // 예정가격결정방법명
  sucsfbidLwltRate: string; // 낙찰하한율
  sucsfbidMthdNm: string; // 낙찰방법명
  rgstDt: string; // 등록일시
  ntceSpecDocUrl1?: string;
  ntceSpecDocUrl2?: string;
  ntceSpecDocUrl3?: string;
  ntceSpecDocUrl4?: string;
  ntceSpecDocUrl5?: string;
  ntceSpecFileNm1?: string;
  ntceSpecFileNm2?: string;
  ntceSpecFileNm3?: string;
  ntceSpecFileNm4?: string;
  ntceSpecFileNm5?: string;
  sptDscrptDocUrl1?: string;
  sptDscrptDocUrl2?: string;
  sptDscrptDocUrl3?: string;
  sptDscrptFileNm1?: string;
  sptDscrptFileNm2?: string;
  sptDscrptFileNm3?: string;
  stdNtceDocUrl?: string;
  stdNtceDocFileNm?: string;
  bidNtceUrl?: string;
  bidNtceDtlUrl?: string;
  cnstrtsiteRgnNm?: string; // 공사현장지역명
  cmmnSpldmdCorpYn?: string; // 공동수급방식명
  mainCnsttyNm?: string; // 주공종명
  indstrytyLmtYn?: string; // 업종제한여부
  indstrytyMfrcFldEvlYn?:string;  // 업종 주력분야 평가 대상 여부
  rgnLmtBidLocplcJdgmBssCd?: string; // 지역제한입찰소재지판단기준코드
  rgnLmtBidLocplcJdgmBssNm?: string; // 지역제한입찰소재지판단기준명
  prtcptPsblRgnNms?: string; // 참가가능지역명 (쉼표구분)
  permsnIndstrytyListNms?: string; // 허용업종목록 (쉼표구분)
  indstrytyMfrcFldListNms?: string; // 주력분야목록 (쉼표구분)
}


export interface BidRecommendation {
  label: string;
  price: number;
  adjRate: number;   // 사정율 (%)
  bidRate: number;    // 투찰률 (%)
}

export interface BidCalculationResult {
  basisAmount: number;
  minSuccessRate: number;
  aValue: number;
  recommendations: BidRecommendation[];
}

export interface BidAValueItem {
  bidNtceNo: string;        // 입찰공고번호
  bidNtceOrd?: string;      // 입찰공고차수
  bidNtceNm?: string;       // 입찰공고명
  bssamt?: string;          // 기초금액
  basePrceAamt?: string;    // 기초금액 A값
  sftyMngcst?: string;      // 산업안전보건관리비
  sftyChckMngcst?: string;  // 안전관리비
  rtrfundNon?: string;      // 퇴직공제부금비
  mrfnHealthInsrprm?: string; // 국민건강보험료
  npnInsrprm?: string;      // 국민연금보험료
  odsnLngtrmrcprInsrprm?: string; // 노인장기요양보험료
  qltyMngcst?: string;     // 품질관리비
  qltyMngcstAObjYn?: string; // 품질관리비A적용대상여부
  envCnsrvcst?: string;     // 환경보전비
  lbrcstBssRate?: string;   // 노무비기준율
  rmrk1?: string;           // 비고1
  rmrk2?: string;           // 비고2
  inptDt?: string;          // 입력일시
  rsrvtnPrceRngBgnRate?: string; // 예비가격범위시작률
  rsrvtnPrceRngEndRate?: string; // 예비가격범위종료율
  etcGnrlexpnsBssRate?: string; // 기타경비기준율
  usefulAmt?: string;       // 가용금액
  resultCode?: string;      // 결과코드
  bssamtOpenDt?: string;    // 기초금액공개일시
  evlBssAmt?: string;       // 평가기준금액
  gnrlMngcstBssRate?: string; // 일반관리비기준율
  scontrctPayprcePayGrntyFee?: string; // 하도급대금지급보증수수료
  dfcltydgrCfcnt?: string;  // 난이도계수
  prftBssRate?: string;     // 이윤기준율
  bidClsfcNo?: string;      // 입찰분류번호
  bidPrceCalclAValYn?: string; // 입찰가격산식A여부
  bssAmtPurcnstcst?: string; // 기초금액순공사비
  smkpAmt?: string;         // 표준시장단가금액 (원화,원)
  smkpAmtYn?: string;       // 표준시장단가금액A적용대상여부
}

export interface PrtcptPsblRgnItem {
  bidNtceNo: string;
  bidNtceOrd?: string;
  lmtSno?: number;
  prtcptPsblRgnNm?: string;
  rgstDt?: string;
  bsnsDivNm?: string;
}

export interface UserLocation {
  location_id: string;
  user_id: string;
  location_name: string;
}

export interface BookmarkWithStatus {
  bookmark_id: string;
  user_id: string;
  bid_notice_no: string;
  bid_notice_name: string;
  bid_notice_ord?: string;
  status: 'interested' | 'bid_completed';
  bid_price?: number;
  notes?: string;
  created_at: string;
  updated_at?: string;
  bid_close_dt?: string;
  openg_dt?: string;
  openg_completed?: boolean;
  actual_bid_price?: string;
  bid_rate?: string;
  rank?: string;
  total_bidders?: number;
  winning_bid_price?: string;
  winning_bid_rate?: string;
}

export interface BidResultItem {
  opengRank?: string;
  prcbdrBizno?: string;
  prcbdrNm?: string;
  prcbdrCeoNm?: string;
  bidprcAmt?: string;
  bidprcrt?: string;
  rmrk?: string;
  bidprcDt?: string;
  opengRsltDivNm?: string;
}

export interface BidResultResponse {
  bid_ntce_no: string;
  results: BidResultItem[];
  user_rank?: BidResultItem;
  total_bidders: number;
}

export interface BusinessProfile {
  business_number: string | null;
  company_name: string | null;
  representative_name: string | null;
}

