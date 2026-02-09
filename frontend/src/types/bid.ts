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
  indstrytyNm?: string; // 업종명
  presmptPrceBgn?: string; // 추정가격시작
  presmptPrceEnd?: string; // 추정가격종료
  bidClseExcpYn?: 'Y' | 'N'; // 입찰마감제외여부
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
}


export interface BidCalculationResult {
  optimalPrice: number;
  minPrice: number;
  recommendedPrice: number;
  calculation: string;
  aValueDetail: string;
}

export interface BidAValueItem {
  bidNtceNo: string;        // 입찰공고번호
  basePrceAamt: string;     // 기초금액 A값 (가장 중요)
  sftyMngcst: string;       // 산업안전보건관리비
  sftyChckMngcst: string;   //	안전관리비
  rtrfundNon: string;       //	퇴직공제부금비
  mrfnHealthInsrprm: string; //	국민건강보험료
  npnInsrprm: string;       //	국민연금보험료
  odsnLngtrmrcprInsrprm: string; //	노인장기요양보험료
  qltyMngcst: string;      //	품질관리비
  qltyMngcstAObjYn: string; //품질관리비A적용대상여부
  smkpAmt: string;          // 표준시장단가금액 (원화,원)
  smkpAmtYn: string;        // 표준시장단가금액A적용대상여부
}

