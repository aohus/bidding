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
  rsrvtnPrceRngBgnRate: '99.855',
  rsrvtnPrceRngEndRate: '103.045',
  ...overrides,
});

const defaultInput = () => ({
  basisAmount: '1000000000',
  bgnRate: '99.855',
  endRate: '103.045',
  aValueItem: makeAValueItem(),
  sucsfbidLwltRate: '87.745',
});

describe('calculateOptimalBidPrice', () => {
  describe('정상 계산 (ok: true)', () => {
    it('Step 1~6 전체 계산이 올바르다', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      // Step 1: estimatedPrice = 1000000000 * (99.855 + 103.045) / 200
      //       = 1000000000 * 202.9 / 200 = round(1014500000) = 1014500000
      expect(result.estimatedPrice).toBe(1014500000);

      // Step 2: A값 = 10M+5M+3M+2M+1.5M+0.5M+1M = 23000000
      expect(result.aValue).toBe(23000000);

      // Step 3: lowerLimitRate = 87.745
      expect(result.lowerLimitRate).toBe(87.745);

      // Step 4: estimatedLowerBound = ceil(((1014500000-23000000)*87.745/100)+23000000)
      //       = ceil((991500000 * 0.87745) + 23000000)
      //       = ceil(869991675 + 23000000) = 892991675
      expect(result.estimatedLowerBound).toBe(892991675);

      // Step 5: optimalBidPrice = ceil(892991675 * 1.001) = 893884667
      expect(result.optimalBidPrice).toBe(Math.ceil(892991675 * 1.001));

      // Step 6: confidence range
      // lbLow = ceil(((1000000000*99.855/100 - 23000000)*87.745/100) + 23000000)
      //       = ceil(((998550000-23000000)*0.87745)+23000000)
      //       = ceil(975550000*0.87745 + 23000000)
      //       = ceil(856101972.5 + 23000000) = 879101973
      expect(result.confidenceRange.low).toBe(
        Math.ceil(((1000000000 * 99.855 / 100 - 23000000) * 87.745 / 100) + 23000000)
      );
      // lbHigh = ceil(((1000000000*103.045/100 - 23000000)*87.745/100) + 23000000)
      expect(result.confidenceRange.high).toBe(
        Math.ceil(((1000000000 * 103.045 / 100 - 23000000) * 87.745 / 100) + 23000000)
      );

      expect(result.basisAmount).toBe(1000000000);
      expect(result.margin).toBe('0.1%');
      expect(result.note).toBe('낙찰하한가 +0.1% 전략');
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

    it('bgnRate가 "0"이면 예비가격 범위 에러', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        bgnRate: '0',
      });

      expect(result.ok).toBe(false);
    });
  });
});
