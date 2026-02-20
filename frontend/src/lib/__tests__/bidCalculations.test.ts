import { describe, it, expect } from 'vitest';
import {
  calculateOptimalBidPrice,
  determineRegionScope,
  determineLicenseGroup,
  determineAmountRange,
} from '../bidCalculations';
import { BidAValueItem } from '@/types/bid';

const makeAValueItem = (overrides: Partial<BidAValueItem> = {}): BidAValueItem => ({
  bidNtceNo: '20260101001',
  bssamt: '1000000000',
  sftyMngcst: '10000000',
  sftyChckMngcst: '5000000',
  rtrfundNon: '3000000',
  mrfnHealthInsrprm: '2000000',
  npnInsrprm: '1500000',
  odsnLngtrmrcprInsrprm: '500000',
  envCnsrvcst: '1000000',
  qltyMngcstAObjYn: 'N',
  qltyMngcst: '0',
  smkpAmtYn: 'N',
  smkpAmt: '0',
  rsrvtnPrceRngBgnRate: '-3',
  rsrvtnPrceRngEndRate: '+3',
  ...overrides,
});

const defaultInput = () => ({
  basisAmount: '1000000000' as string | number | undefined | null,
  fallbackBasisAmount: undefined as string | number | undefined | null,
  aValueItem: makeAValueItem(),
  sucsfbidLwltRate: '87.745' as string | undefined,
  prtcptPsblRgnNms: '경기도' as string | undefined,
  permsnIndstrytyListNms: '토공사업' as string | undefined,
});

describe('determineRegionScope', () => {
  it('undefined → province', () => {
    expect(determineRegionScope(undefined)).toBe('province');
  });

  it('"경기도" (단일 도) → province', () => {
    expect(determineRegionScope('경기도')).toBe('province');
  });

  it('"서울특별시, 경기도" (콤마) → province', () => {
    expect(determineRegionScope('서울특별시, 경기도')).toBe('province');
  });

  it('"경기도 수원시, 경기도 성남시" (콤마) → province', () => {
    expect(determineRegionScope('경기도 수원시, 경기도 성남시')).toBe('province');
  });

  it('"경기도 성남시" (도+시) → city', () => {
    expect(determineRegionScope('경기도 성남시')).toBe('city');
  });

  it('"강원도 춘천시" (도+시) → city', () => {
    expect(determineRegionScope('강원도 춘천시')).toBe('city');
  });

  it('"경기도 양평군" (도+군) → city', () => {
    expect(determineRegionScope('경기도 양평군')).toBe('city');
  });

  it('"서울특별시 강남구" (시+구) → city', () => {
    expect(determineRegionScope('서울특별시 강남구')).toBe('city');
  });

  it('"전국" → province', () => {
    expect(determineRegionScope('전국')).toBe('province');
  });
});

describe('determineLicenseGroup', () => {
  it('undefined → general', () => {
    expect(determineLicenseGroup(undefined)).toBe('general');
  });

  it('"토공사업" → general', () => {
    expect(determineLicenseGroup('토공사업')).toBe('general');
  });

  it('"조경식재ㆍ시설물공사업" → landscaping', () => {
    expect(determineLicenseGroup('조경식재ㆍ시설물공사업')).toBe('landscaping');
  });

  it('"나무병원(1종)" → landscaping', () => {
    expect(determineLicenseGroup('나무병원(1종)')).toBe('landscaping');
  });

  it('"일반건설업, 조경식재공사업" → landscaping', () => {
    expect(determineLicenseGroup('일반건설업, 조경식재공사업')).toBe('landscaping');
  });
});

describe('determineAmountRange', () => {
  it('50,000,000 (5천만) → under1', () => {
    expect(determineAmountRange(50_000_000)).toBe('under1');
  });

  it('99,999,999 → under1', () => {
    expect(determineAmountRange(99_999_999)).toBe('under1');
  });

  it('100,000,000 (1억) → from1to3', () => {
    expect(determineAmountRange(100_000_000)).toBe('from1to3');
  });

  it('200,000,000 (2억) → from1to3', () => {
    expect(determineAmountRange(200_000_000)).toBe('from1to3');
  });

  it('299,999,999 → from1to3', () => {
    expect(determineAmountRange(299_999_999)).toBe('from1to3');
  });

  it('300,000,000 (3억) → over3', () => {
    expect(determineAmountRange(300_000_000)).toBe('over3');
  });

  it('1,000,000,000 (10억) → over3', () => {
    expect(determineAmountRange(1_000_000_000)).toBe('over3');
  });
});

describe('calculateOptimalBidPrice', () => {
  describe('사정율 lookup (지역 × 면허 × 금액)', () => {
    it('도 + 전체면허 + 3억이상 → 100.140', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '500000000',
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(100.140);
    });

    it('도 + 전체면허 + 1억미만 → 99.930', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '80000000',
        aValueItem: makeAValueItem({ bssamt: '80000000' }),
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(99.930);
    });

    it('도 + 전체면허 + 1~3억 → 100.092', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '200000000',
        aValueItem: makeAValueItem({ bssamt: '200000000' }),
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(100.092);
    });

    it('도 + 조경/나무 + 1~3억 → 99.822', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도',
        permsnIndstrytyListNms: '조경식재ㆍ시설물공사업',
        basisAmount: '200000000',
        aValueItem: makeAValueItem({ bssamt: '200000000' }),
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(99.822);
    });

    it('도 + 조경/나무 + 3억이상 → 99.502', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도',
        permsnIndstrytyListNms: '나무병원(1종)',
        basisAmount: '500000000',
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(99.502);
    });

    it('시군 + 전체면허 + 1억미만 → 99.536', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도 성남시',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '80000000',
        aValueItem: makeAValueItem({ bssamt: '80000000' }),
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(99.536);
    });

    it('시군 + 전체면허 + 1~3억 → 99.994', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도 수원시',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '200000000',
        aValueItem: makeAValueItem({ bssamt: '200000000' }),
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(99.994);
    });

    it('콤마(여러 지역) → province 처리 → 도 rate 적용', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '서울특별시, 경기도',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '500000000',
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(100.140);
    });
  });

  describe('fallback 사정율', () => {
    it('시군 + 전체면허 + 3억이상 (시군에 없음) → 도 rate fallback → 100.140', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도 성남시',
        permsnIndstrytyListNms: '토공사업',
        basisAmount: '500000000',
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(100.140);
    });

    it('시군 + 조경/나무 + 1~3억 (시군에 조경 없음) → 도+조경 fallback → 99.822', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: '경기도 성남시',
        permsnIndstrytyListNms: '조경식재ㆍ시설물공사업',
        basisAmount: '200000000',
        aValueItem: makeAValueItem({ bssamt: '200000000' }),
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(99.822);
    });

    it('지역/면허 미제공 시 기본값 (province + general)', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        prtcptPsblRgnNms: undefined,
        permsnIndstrytyListNms: undefined,
      });
      if (!result.ok) throw new Error('expected ok');
      expect(result.assessmentRate).toBe(100.140);
    });
  });

  describe('정상 계산 (ok: true)', () => {
    it('도 + 전체면허 + 3억이상 전체 계산', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      // assessmentRate = 100.140 (province + general + over3)
      expect(result.assessmentRate).toBe(100.140);

      // estimatedPrice = 1,000,000,000 × 100.140 / 100 = 1,001,400,000
      expect(result.estimatedPrice).toBe(Math.round(1000000000 * 100.140 / 100));

      // A값 = 10M+5M+3M+2M+1.5M+0.5M+1M = 23,000,000
      expect(result.aValue).toBe(23000000);

      expect(result.lowerLimitRate).toBe(87.745);

      // estimatedLowerBound
      expect(result.estimatedLowerBound).toBe(
        Math.ceil(((result.estimatedPrice - 23000000) * 87.745 / 100) + 23000000)
      );

      // optimalBidPrice = ceil(estimatedLowerBound * 1.001)
      expect(result.optimalBidPrice).toBe(
        Math.ceil(result.estimatedLowerBound * 1.001)
      );

      // confidence range
      expect(result.confidenceRange.low).toBe(
        Math.ceil(((1000000000 * 97 / 100 - 23000000) * 87.745 / 100) + 23000000)
      );
      expect(result.confidenceRange.high).toBe(
        Math.ceil(((1000000000 * 103 / 100 - 23000000) * 87.745 / 100) + 23000000)
      );

      expect(result.basisAmount).toBe(1000000000);
      expect(result.usedFallback).toBe(false);
    });

    it('qltyMngcst와 smkpAmt가 Y이면 A값에 포함', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        aValueItem: makeAValueItem({
          qltyMngcstAObjYn: 'Y',
          qltyMngcst: '2000000',
          smkpAmtYn: 'Y',
          smkpAmt: '3000000',
        }),
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.aValue).toBe(28000000);
    });

    it('aValueItem이 null이면 A값은 0', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        aValueItem: null,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.aValue).toBe(0);
      expect(result.optimalBidPrice).toBeGreaterThan(0);
    });

    it('sucsfbidLwltRate가 없으면 87.745 기본값', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        sucsfbidLwltRate: undefined,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.lowerLimitRate).toBe(87.745);
    });

    it('confidenceRange.low < estimatedLowerBound < confidenceRange.high', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      expect(result.confidenceRange.low).toBeLessThan(result.estimatedLowerBound);
      expect(result.estimatedLowerBound).toBeLessThan(result.confidenceRange.high);
    });
  });

  describe('fallback (배정예산금액)', () => {
    it('bssamt 없으면 fallbackBasisAmount를 사용', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: undefined,
        fallbackBasisAmount: '500000000',
        aValueItem: makeAValueItem({ bssamt: undefined }),
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.basisAmount).toBe(500000000);
      expect(result.usedFallback).toBe(true);
    });

    it('bssamt가 0이면 fallbackBasisAmount를 사용', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: '0',
        fallbackBasisAmount: '500000000',
        aValueItem: makeAValueItem({ bssamt: '0' }),
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.usedFallback).toBe(true);
      expect(result.basisAmount).toBe(500000000);
    });
  });

  describe('에러 케이스 (ok: false)', () => {
    it('basisAmount와 fallbackBasisAmount 모두 없으면 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: undefined,
        fallbackBasisAmount: undefined,
      });

      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toContain('기초금액');
    });

    it('basisAmount가 빈 문자열이고 fallback도 없으면 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: '',
        fallbackBasisAmount: undefined,
      });

      expect(result.ok).toBe(false);
    });

    it('basisAmount가 NaN이고 fallback도 없으면 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: NaN,
        fallbackBasisAmount: undefined,
      });

      expect(result.ok).toBe(false);
    });
  });
});
