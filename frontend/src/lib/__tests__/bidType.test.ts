import { describe, it, expect } from 'vitest';
import { inferBidType } from '../bidType';

describe('inferBidType', () => {
  it('주공종명이 있으면 공사(cnstwk)', () => {
    expect(inferBidType({ mainCnsttyNm: '조경식재공사업' })).toBe('cnstwk');
  });

  it('공사현장지역명만 있어도 공사(cnstwk)', () => {
    expect(inferBidType({ cnstrtsiteRgnNm: '서울특별시' })).toBe('cnstwk');
  });

  it('둘 다 없으면 용역(servc)', () => {
    expect(inferBidType({})).toBe('servc');
    expect(inferBidType({ mainCnsttyNm: '', cnstrtsiteRgnNm: '' })).toBe('servc');
  });
});
