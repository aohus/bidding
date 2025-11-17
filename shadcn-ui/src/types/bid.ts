export interface BidSearchParams {
  inqryDiv: '1' | '2'; // 1:공고게시일시, 2:개찰일시
  inqryBgnDt: string; // YYYYMMDDHHMM
  inqryEndDt: string; // YYYYMMDDHHMM
  prtcptLmtRgnCd?: string; // 참가제한지역코드
  presmptPrceBgn?: string; // 추정가격시작
  presmptPrceEnd?: string; // 추정가격종료
  numOfRows?: number;
  pageNo?: number;
  ServiceKey: string;
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
  ntceSpecFileNm1?: string; // 공고규격서파일명1
  ntceSpecFileNm2?: string; // 공고규격서파일명2
  ntceSpecFileNm3?: string; // 공고규격서파일명3
  ntceSpecFileNm4?: string; // 공고규격서파일명4
  ntceSpecFileNm5?: string; // 공고규격서파일명5
  sptDscrptDocUrl1?: string;
  sptDscrptDocUrl2?: string;
  sptDscrptDocUrl3?: string;
  sptDscrptFileNm1?: string; // 현장설명서파일명1
  sptDscrptFileNm2?: string; // 현장설명서파일명2
  sptDscrptFileNm3?: string; // 현장설명서파일명3
  stdNtceDocUrl?: string;
  stdNtceDocFileNm?: string; // 표준공고서파일명
  bidNtceUrl?: string;
  bidNtceDtlUrl?: string;
  cnstrtsiteRgnNm?: string; // 공사현장지역명
  cmmnSpldmdCorpYn?: string; // 공동수급방식명
  indutyLmtYn?: string; // 업종제한여부
}

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

export interface BidCalculationResult {
  optimalPrice: number;
  minPrice: number;
  maxPrice: number;
  recommendedPrice: number;
  calculation: string;
}