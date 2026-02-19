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

// API 상대값(-3, +3) → 절대값(97, 103)
const defaultInput = () => ({
  basisAmount: '1000000000',
  bgnRate: '-3',
  endRate: '+3',
  aValueItem: makeAValueItem(),
  sucsfbidLwltRate: '87.745',
});

describe('calculateOptimalBidPrice', () => {
  describe('정상 계산 (ok: true)', () => {
    it('API 상대값(-3, +3)으로 전체 계산이 올바르다', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      // 상대값 → 절대값: bgnRate=97, endRate=103
      // Step 1: estimatedPrice = 1000000000 * (97 + 103) / 200
      //       = 1000000000 * 200 / 200 = 1000000000
      expect(result.estimatedPrice).toBe(1000000000);

      // Step 2: A값 = 10M+5M+3M+2M+1.5M+0.5M+1M = 23000000
      expect(result.aValue).toBe(23000000);

      // Step 3: lowerLimitRate = 87.745
      expect(result.lowerLimitRate).toBe(87.745);

      // Step 4: estimatedLowerBound = ceil(((1000000000-23000000)*87.745/100)+23000000)
      //       = ceil((977000000 * 0.87745) + 23000000)
      //       = ceil(857268650 + 23000000) = 880268650
      expect(result.estimatedLowerBound).toBe(
        Math.ceil(((1000000000 - 23000000) * 87.745 / 100) + 23000000)
      );

      // Step 5: optimalBidPrice = ceil(estimatedLowerBound * 1.001)
      expect(result.optimalBidPrice).toBe(
        Math.ceil(result.estimatedLowerBound * 1.001)
      );

      // Step 6: confidence range (절대값 97%, 103% 기준)
      expect(result.confidenceRange.low).toBe(
        Math.ceil(((1000000000 * 97 / 100 - 23000000) * 87.745 / 100) + 23000000)
      );
      expect(result.confidenceRange.high).toBe(
        Math.ceil(((1000000000 * 103 / 100 - 23000000) * 87.745 / 100) + 23000000)
      );

      expect(result.basisAmount).toBe(1000000000);
      expect(result.margin).toBe('0.1%');
      expect(result.note).toBe('낙찰하한가 +0.1% 전략');
    });

    it('절대값 rate(99.855, 103.045)도 올바르게 처리한다', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        bgnRate: '99.855',
        endRate: '103.045',
        aValueItem: makeAValueItem({
          rsrvtnPrceRngBgnRate: '99.855',
          rsrvtnPrceRngEndRate: '103.045',
        }),
      });
      if (!result.ok) throw new Error('expected ok');

      // |99.855| > 50 → 절대값으로 판단
      expect(result.estimatedPrice).toBe(
        Math.round(1000000000 * (99.855 + 103.045) / 200)
      );
    });

    it('용역 상대값(-2, +2)으로 올바르게 계산한다', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        bgnRate: '-2',
        endRate: '+2',
        aValueItem: makeAValueItem({
          rsrvtnPrceRngBgnRate: '-2',
          rsrvtnPrceRngEndRate: '+2',
        }),
      });
      if (!result.ok) throw new Error('expected ok');

      // 절대값: 98, 102
      expect(result.estimatedPrice).toBe(
        Math.round(1000000000 * (98 + 102) / 200)
      );
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

    it('상대값 0은 유효하다 (100%를 의미)', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        bgnRate: '0',
        endRate: '0',
      });
      if (!result.ok) throw new Error('expected ok');

      // 0 → 100 + 0 = 100%, estimatedPrice = basisAmount * 200/200 = basisAmount
      expect(result.estimatedPrice).toBe(1000000000);
    });
  });

  describe('에러 케이스 (ok: false)', () => {
    it('basisAmount가 undefined이면 기초금액 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: undefined,
      });

      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toContain('기초금액');
    });

    it('basisAmount가 빈 문자열이면 기초금액 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: '',
      });

      expect(result.ok).toBe(false);
    });

    it('basisAmount가 0이면 기초금액 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: '0',
      });

      expect(result.ok).toBe(false);
    });

    it('basisAmount가 NaN이면 기초금액 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: NaN,
      });

      expect(result.ok).toBe(false);
    });

    it('bgnRate가 없으면 예비가격 범위 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        bgnRate: undefined,
      });

      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toContain('예비가격 범위');
    });

    it('endRate가 빈 문자열이면 예비가격 범위 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        endRate: '',
      });

      expect(result.ok).toBe(false);
    });
  });
});
