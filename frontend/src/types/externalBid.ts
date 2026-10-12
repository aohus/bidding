/**
 * 외부기관(비-나라장터) 입찰공고 타입.
 *
 * 나라장터 BidItem 과 의도적으로 분리한다. 기관마다 제공 필드가 달라
 * BidItem 모양에 맞추면 대부분이 null 인 가짜 호환이 된다.
 * 백엔드 스키마: backend/app/schemas/external_bid.py
 */

/** 기관 식별자. 백엔드 external_bid_notices.source 와 동일. */
export type ExternalSourceId =
  | 'lh'
  | 'kwater'
  | 'kdhc'
  | 'kra'
  | 'kogas'
  | 'kepco';

export interface ExternalBidItem {
  source: string;
  sourceName: string;
  noticeNo: string;
  noticeOrd: string;
  title: string | null;
  institution: string | null;
  workDiv: string | null;
  cntrctMthd: string | null;
  /** 공고/등록일시 YYYYMMDDHHMM */
  rgstDt: string | null;
  /** 입찰마감일시 YYYYMMDDHHMM */
  bidCloseDt: string | null;
  /** 개찰일시 YYYYMMDDHHMM */
  opengDt: string | null;
  presmptPrce: number | null;
  status: string | null;
  /** 기관별 고유 필드 전체 (정규화 컬럼에 없는 값) */
  raw: Record<string, unknown>;
}

export interface ExternalBidListResponse {
  items: ExternalBidItem[];
  totalCount: number;
  numOfRows: number;
  pageNo: number;
}

export interface ExternalBidResultItem {
  source: string;
  sourceName: string;
  noticeNo: string;
  noticeOrd: string;
  seq: number;
  title: string | null;
  bidderNm: string | null;
  bidderAmt: number | null;
  statusNm: string | null;
  opengDt: string | null;
  raw: Record<string, unknown>;
}

export interface ExternalBidResultListResponse {
  items: ExternalBidResultItem[];
  totalCount: number;
  numOfRows: number;
  pageNo: number;
}

export interface ExternalSourceInfo {
  source: string;
  name: string;
  /** 'day' | 'month' — 수자원은 월 단위 조회만 가능 */
  granularity: string;
}

export interface ExternalSourceListResponse {
  sources: ExternalSourceInfo[];
}

/** 검색 폼이 다루는 사용자 입력. 날짜는 YYYY-MM-DD. */
export interface ExternalBidSearchInput {
  sources: string[];
  dateFrom: string;
  dateTo: string;
  keyword: string;
}
