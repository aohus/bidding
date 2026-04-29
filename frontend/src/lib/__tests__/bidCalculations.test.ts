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
    it('추정 낙찰하한가 = round((expectedPresumedPrice - aValue) × lowerLimitRate/100 + aValue)', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      // A값 = 10M+5M+3M+2M+1.5M+0.5M+1M = 23,000,000
      expect(result.aValue).toBe(23_000_000);
      expect(result.lowerLimitRate).toBe(87.745);
      expect(result.basisAmount).toBe(1_000_000_000);

      // expectedReserveRate 미지정 → 1.0 fallback
      // expectedPresumedPrice = 1,000,000,000 × 1.0 = 1,000,000,000
      const expectedLowerBound = Math.round(
        ((1_000_000_000 - 23_000_000) * 87.745) / 100 + 23_000_000,
      );
      expect(result.estimatedLowerBound).toBe(expectedLowerBound);
    });

    it('추천 투찰금액 = 추정 낙찰하한가 (default marginWon=0)', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      expect(result.optimalBidPrice).toBe(result.estimatedLowerBound);
      // FIXED_MARGIN export 호환성 유지 (deprecated, default marginWon=0)
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
      expect(result.optimalBidPrice).toBe(902_300_000);
    });

    it('A값이 0일 때: optimalBidPrice = round(basisAmount × lowerLimitRate/100)', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        aValueItem: null,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.aValue).toBe(0);
      const expected = Math.round((1_000_000_000 * 87.745) / 100);
      expect(result.estimatedLowerBound).toBe(expected);
      expect(result.optimalBidPrice).toBe(expected);
    });

    it('round 반올림 경계 검증 (87.7451% × 1억)', () => {
      // (100,000,001 - 0) × 87.7451 / 100
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        basisAmount: '100000001',
        aValueItem: null,
        sucsfbidLwltRate: '87.7451',
      });
      if (!result.ok) throw new Error('expected ok');

      const raw = (100_000_001 * 87.7451) / 100;
      expect(result.estimatedLowerBound).toBe(Math.round(raw));
      expect(result.optimalBidPrice).toBe(Math.round(raw));
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

    it('margin 표기 = "없음" (default marginWon=0)', () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      expect(result.margin).toBe('없음');
    });

    it('expectedReserveRate=0.97 적용 시 추정 예정가격 = basisAmount × 0.97', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0.97,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(0.97);
      expect(result.expectedPresumedPrice).toBe(Math.round(1_000_000_000 * 0.97));
    });

    it('expectedReserveRate=1.03 적용 시 추정 예정가격 = basisAmount × 1.03', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 1.03,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(1.03);
      expect(result.expectedPresumedPrice).toBe(Math.round(1_000_000_000 * 1.03));
    });

    it("expectedReserveRate 미지정 시 1.0 fallback + reserveRateSource='fallback_default'", () => {
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(1.0);
      expect(result.reserveRateSource).toBe('fallback_default');
      expect(result.expectedPresumedPrice).toBe(1_000_000_000);
    });

    it('marginWon=1000 옵션 시 optimalBidPrice = estimatedLowerBound + 1000 + margin="+1,000원"', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        marginWon: 1000,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.optimalBidPrice).toBe(result.estimatedLowerBound + 1000);
      expect(result.margin).toBe('+1,000원');
      expect(result.note).toBe('낙찰하한가 + 1,000원 전략');
    });

    it("reserveRateSource='group_avg' 전달 시 result에 그대로 반영", () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0.985,
        reserveRateSource: 'group_avg',
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.reserveRateSource).toBe('group_avg');
      expect(result.expectedReserveRate).toBe(0.985);
    });

    it('expectedReserveRate는 퍼센트 소수 셋째자리 기준으로 반올림 적용', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0.9987654,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(0.99877);
      expect(result.expectedPresumedPrice).toBe(Math.round(1_000_000_000 * 0.99877));
    });

    it('expectedReserveRate=0.97일 때 estimatedLowerBound 정확히 계산', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0.97,
      });
      if (!result.ok) throw new Error('expected ok');

      // expectedPresumedPrice = round(1,000,000,000 × 0.97) = 970,000,000
      // estimatedLowerBound = round((970,000,000 - 23,000,000) × 87.745 / 100 + 23,000,000)
      const expectedPresumedPrice = Math.round(1_000_000_000 * 0.97);
      const expected = Math.round(
        ((expectedPresumedPrice - 23_000_000) * 87.745) / 100 + 23_000_000,
      );
      expect(result.estimatedLowerBound).toBe(expected);
    });

    it('confidenceRange는 사정율 ±3%p 변동 기반 (이중 곱 없음)', () => {
      // default rate=1.0 → [0.97, 1.03] basisAmount → 기존 동작 보존
      const result = calculateOptimalBidPrice(defaultInput());
      if (!result.ok) throw new Error('expected ok');

      const aValue = 23_000_000;
      const rate = 87.745;
      const lb = (presumed: number) =>
        Math.round(((presumed - aValue) * rate) / 100 + aValue);

      expect(result.confidenceRange.low).toBe(lb(1_000_000_000 * 0.97));
      expect(result.confidenceRange.high).toBe(lb(1_000_000_000 * 1.03));
    });

    it('사정율 0.97일 때도 estimatedLowerBound이 신뢰구간 내부에 위치', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0.97,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.confidenceRange.low).toBeLessThan(result.estimatedLowerBound);
      expect(result.estimatedLowerBound).toBeLessThan(result.confidenceRange.high);
    });
  });

  describe('입력 검증 (sanitization)', () => {
    it('expectedReserveRate가 음수면 1.0 fallback', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: -0.5,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(1.0);
    });

    it('expectedReserveRate가 0이면 1.0 fallback', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(1.0);
    });

    it('expectedReserveRate가 NaN이면 1.0 fallback', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: NaN,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(1.0);
    });

    it('expectedReserveRate가 너무 크면 1.5로 클램프', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 5.0,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(1.5);
    });

    it('expectedReserveRate가 너무 작으면 0.5로 클램프', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        expectedReserveRate: 0.1,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.expectedReserveRate).toBe(0.5);
    });

    it('marginWon이 음수면 0으로 클램프', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        marginWon: -5000,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.optimalBidPrice).toBe(result.estimatedLowerBound);
      expect(result.margin).toBe('없음');
    });

    it('marginWon이 NaN이면 0으로 fallback', () => {
      const result = calculateOptimalBidPrice({
        ...defaultInput(),
        marginWon: NaN,
      });
      if (!result.ok) throw new Error('expected ok');

      expect(result.optimalBidPrice).toBe(result.estimatedLowerBound);
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
