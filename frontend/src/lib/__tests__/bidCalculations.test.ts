import { describe, it, expect } from 'vitest';
import { calculateOptimalBidPrice } from '../bidCalculations';
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
  basisAmount: '1000000000',
  fallbackBasisAmount: undefined as string | undefined,
  priceRangeEndRate: '+3' as string | undefined,
  aValueItem: makeAValueItem(),
  sucsfbidLwltRate: '87.745',
});

describe('calculateOptimalBidPrice', () => {
  describe('사정율 결정', () => {
    it('±3 범위 → 사정율 99.7%', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        priceRangeEndRate: '+3',
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.assessmentRate).toBe(99.7);
      expect(result.estimatedPrice).toBe(Math.round(1000000000 * 99.7 / 100));
    });

    it('±2 범위 → 사정율 99.9%', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        priceRangeEndRate: '+2',
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.assessmentRate).toBe(99.9);
      expect(result.estimatedPrice).toBe(Math.round(1000000000 * 99.9 / 100));
    });

    it('endRate 없으면 기본 사정율 99.7%', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        priceRangeEndRate: undefined,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.assessmentRate).toBe(99.7);
    });

    it('절대값 endRate 103 → ±3 범위 → 사정율 99.7%', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        priceRangeEndRate: '103',
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.assessmentRate).toBe(99.7);
    });

    it('절대값 endRate 102 → ±2 범위 → 사정율 99.9%', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        priceRangeEndRate: '102',
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.assessmentRate).toBe(99.9);
    });
  });

  describe('정상 계산 (ok: true)', () => {
    it('공사(±3) 전체 계산이 올바르다', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      // Step 1: estimatedPrice = 1000000000 × 99.7 / 100 = 997000000
      expect(result.estimatedPrice).toBe(997000000);

      // Step 2: A값 = 10M+5M+3M+2M+1.5M+0.5M+1M = 23000000
      expect(result.aValue).toBe(23000000);

      // Step 3: lowerLimitRate = 87.745
      expect(result.lowerLimitRate).toBe(87.745);

      // Step 4: estimatedLowerBound
      expect(result.estimatedLowerBound).toBe(
        Math.ceil(((997000000 - 23000000) * 87.745 / 100) + 23000000)
      );

      // Step 5: optimalBidPrice = ceil(estimatedLowerBound * 1.001)
      expect(result.optimalBidPrice).toBe(
        Math.ceil(result.estimatedLowerBound * 1.001)
      );

      // Step 6: confidence range (고정 97%, 103% 기준)
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
