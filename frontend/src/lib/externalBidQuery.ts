/**
 * 외부기관 공고 조회 쿼리 생성 및 표시 포맷.
 *
 * 컴포넌트에서 분리한 이유: 날짜 변환과 "값 없음" 표시 규칙이 이 기능의
 * 실질적인 로직이라 단독으로 테스트할 수 있어야 한다.
 */

import type { ExternalBidSearchInput } from '@/types/externalBid';

const DATE_DIGITS = 8;
const DT14_LENGTH = 12;

function digitsOnly(value: string): string {
  return value.replace(/\D/g, '');
}

/** YYYY-MM-DD → YYYYMMDD0000. 날짜를 만들 수 없으면 undefined. */
export function toDayStart(date: string): string | undefined {
  const digits = digitsOnly(date ?? '');
  if (digits.length < DATE_DIGITS) return undefined;
  return `${digits.slice(0, DATE_DIGITS)}0000`;
}

/** YYYY-MM-DD → YYYYMMDD2359. 날짜를 만들 수 없으면 undefined. */
export function toDayEnd(date: string): string | undefined {
  const digits = digitsOnly(date ?? '');
  if (digits.length < DATE_DIGITS) return undefined;
  return `${digits.slice(0, DATE_DIGITS)}2359`;
}

/**
 * GET /external-bids 쿼리스트링을 만듭니다.
 *
 * 빈 값은 보내지 않는다 — 빈 문자열을 보내면 백엔드가 그대로 필터로 받아
 * 결과가 0건이 된다. keyword 는 가공하지 않는다(백엔드가 LIKE 와일드카드를
 * 이스케이프하므로 여기서 또 건드리면 이중 처리된다).
 */
export function buildExternalBidQuery(
  input: ExternalBidSearchInput,
  pageNo: number,
  numOfRows: number,
): URLSearchParams {
  const query = new URLSearchParams();
  query.set('pageNo', String(pageNo));
  query.set('numOfRows', String(numOfRows));

  const sources = input.sources.filter(Boolean);
  if (sources.length > 0) {
    query.set('source', sources.join(','));
  }

  const from = toDayStart(input.dateFrom);
  if (from) query.set('dateFrom', from);

  const to = toDayEnd(input.dateTo);
  if (to) query.set('dateTo', to);

  const keyword = (input.keyword ?? '').trim();
  if (keyword) query.set('keyword', keyword);

  return query;
}

/**
 * YYYYMMDDHHMM → 'YYYY-MM-DD HH:mm'.
 *
 * 시각이 0000 이면 날짜만 보여준다 — 날짜만 제공하는 기관(LH, 지역난방)의
 * 값이 0000 으로 정규화되므로, '00:00' 으로 표시하면 자정이라는 오해를 준다.
 */
export function formatDateTime14(value: string | null | undefined): string {
  const digits = digitsOnly(value ?? '');
  if (digits.length < DATE_DIGITS) return '-';

  const padded = digits.slice(0, DT14_LENGTH).padEnd(DT14_LENGTH, '0');
  const date = `${padded.slice(0, 4)}-${padded.slice(4, 6)}-${padded.slice(6, 8)}`;
  const time = `${padded.slice(8, 10)}:${padded.slice(10, 12)}`;
  return time === '00:00' ? date : `${date} ${time}`;
}

/**
 * 금액 표시. 값이 없거나 0 이면 '-'.
 *
 * 0 을 '0' 으로 표시하면 안 된다 — 가스공사처럼 추정가격을 아예 제공하지
 * 않는 기관이 있어, 미공개를 '0원'으로 오인하게 된다.
 */
export function formatPrice(value: number | null | undefined): string {
  if (!value) return '-';
  return value.toLocaleString();
}
