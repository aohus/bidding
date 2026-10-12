import { describe, it, expect } from 'vitest';
import {
  buildExternalBidQuery,
  formatDateTime14,
  formatPrice,
  toDayEnd,
  toDayStart,
} from '../externalBidQuery';

describe('toDayStart / toDayEnd', () => {
  it('converts YYYY-MM-DD to window bounds', () => {
    expect(toDayStart('2026-10-08')).toBe('202610080000');
    expect(toDayEnd('2026-10-08')).toBe('202610082359');
  });

  it('accepts a date already stripped of separators', () => {
    expect(toDayStart('20261008')).toBe('202610080000');
  });

  it('returns undefined for empty or unusable input', () => {
    expect(toDayStart('')).toBeUndefined();
    expect(toDayEnd('')).toBeUndefined();
    expect(toDayStart('2026')).toBeUndefined();
  });
});

describe('buildExternalBidQuery', () => {
  const base = { sources: [], dateFrom: '', dateTo: '', keyword: '' };

  it('always sends paging params', () => {
    const q = buildExternalBidQuery(base, 2, 50);
    expect(q.get('pageNo')).toBe('2');
    expect(q.get('numOfRows')).toBe('50');
  });

  it('joins selected sources with commas', () => {
    const q = buildExternalBidQuery({ ...base, sources: ['lh', 'kepco'] }, 1, 100);
    expect(q.get('source')).toBe('lh,kepco');
  });

  it('omits source when nothing is selected', () => {
    const q = buildExternalBidQuery(base, 1, 100);
    expect(q.has('source')).toBe(false);
  });

  it('converts dates to window bounds', () => {
    const q = buildExternalBidQuery(
      { ...base, dateFrom: '2026-10-01', dateTo: '2026-10-12' },
      1,
      100,
    );
    expect(q.get('dateFrom')).toBe('202610010000');
    expect(q.get('dateTo')).toBe('202610122359');
  });

  it('omits either date independently', () => {
    const q = buildExternalBidQuery({ ...base, dateFrom: '2026-10-01' }, 1, 100);
    expect(q.get('dateFrom')).toBe('202610010000');
    expect(q.has('dateTo')).toBe(false);
  });

  it('trims and omits a blank keyword', () => {
    expect(buildExternalBidQuery({ ...base, keyword: '   ' }, 1, 100).has('keyword')).toBe(false);
    expect(buildExternalBidQuery({ ...base, keyword: ' 공사 ' }, 1, 100).get('keyword')).toBe('공사');
  });

  it('passes the keyword through without manual escaping', () => {
    // 백엔드가 LIKE 와일드카드를 이스케이프한다. 프론트에서 또 건드리면 이중 처리된다.
    const q = buildExternalBidQuery({ ...base, keyword: '100%_공사' }, 1, 100);
    expect(q.get('keyword')).toBe('100%_공사');
  });
});

describe('formatDateTime14', () => {
  it('formats a full timestamp', () => {
    expect(formatDateTime14('202610161400')).toBe('2026-10-16 14:00');
  });

  it('drops the time when it is midnight (date-only source)', () => {
    // 지역난방/LH 등은 날짜만 제공해 0000 으로 정규화된다.
    expect(formatDateTime14('202610080000')).toBe('2026-10-08');
  });

  it('returns a dash for missing values', () => {
    expect(formatDateTime14(null)).toBe('-');
    expect(formatDateTime14('')).toBe('-');
  });

  it('returns a dash for malformed values rather than slicing garbage', () => {
    expect(formatDateTime14('2026')).toBe('-');
  });
});

describe('formatPrice', () => {
  it('formats with thousands separators', () => {
    expect(formatPrice(31264170000)).toBe('31,264,170,000');
  });

  it('returns a dash when the agency does not provide a price', () => {
    // 가스공사는 추정가격 필드가 아예 없다 — 0 원으로 보이면 오인된다.
    expect(formatPrice(null)).toBe('-');
    expect(formatPrice(0)).toBe('-');
  });
});
