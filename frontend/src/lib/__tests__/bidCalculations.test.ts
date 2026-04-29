import { describe, it, expect } from 'vitest';
import { calculateOptimalBidPrice, FIXED_MARGIN } from '../bidCalculations';
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
});

describe('calculateOptimalBidPrice (새 공식)', () => {
  describe('정상 계산 (ok: true)', () => {
    it('추정 낙찰하한가 = round((basisAmount - aValue) × lowerLimitRate/100 + aValue)', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      // A값 = 10M+5M+3M+2M+1.5M+0.5M+1M = 23,000,000
      expect(result.aValue).toBe(23_000_000);
      expect(result.lowerLimitRate).toBe(87.745);
      expect(result.basisAmount).toBe(1_000_000_000);

      const expectedLowerBound = Math.round(
        ((1_000_000_000 - 23_000_000) * 87.745) / 100 + 23_000_000,
      );
      expect(result.estimatedLowerBound).toBe(expectedLowerBound);
    });

    it('추천 투찰금액 = 추정 낙찰하한가 + 1,000원', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      expect(result.optimalBidPrice).toBe(result.estimatedLowerBound + FIXED_MARGIN);
      expect(FIXED_MARGIN).toBe(1000);
    });

    it('낙찰하한율 90% 검증', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        sucsfbidLwltRate: '90',
      });
      if (!result.ok) throw new Error('expected ok');

      // (1,000,000,000 - 23,000,000) × 0.90 + 23,000,000 = 902,300,000
      expect(result.estimatedLowerBound).toBe(902_300_000);
      expect(result.optimalBidPrice).toBe(902_301_000);
    });

    it('A값이 0일 때: optimalBidPrice = round(basisAmount × lowerLimitRate/100) + 1000', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        aValueItem: null,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.aValue).toBe(0);
      const expected = Math.round((1_000_000_000 * 87.745) / 100);
      expect(result.estimatedLowerBound).toBe(expected);
      expect(result.optimalBidPrice).toBe(expected + 1000);
    });

    it('round 반올림 경계 검증 (87.7451% × 1억)', () => {
      // (100,000,000 - 0) × 87.7451 / 100 = 87,745,100.0
      // 1원 미만 분수 발생 시 round 동작 확인
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: '100000001',
        aValueItem: null,
        sucsfbidLwltRate: '87.7451',
      });
      if (!result.ok) throw new Error('expected ok');

      const raw = (100_000_001 * 87.7451) / 100;
      expect(result.estimatedLowerBound).toBe(Math.round(raw));
      expect(result.optimalBidPrice).toBe(Math.round(raw) + 1000);
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

      expect(result.aValue).toBe(28_000_000);
    });

    it('sucsfbidLwltRate 없으면 87.745 기본값', () => {
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

    it('margin 표기 = "+1,000원"', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      expect(result.margin).toBe('+1,000원');
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

      expect(result.basisAmount).toBe(500_000_000);
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
      expect(result.basisAmount).toBe(500_000_000);
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
