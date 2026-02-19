import { describe, it, expect } from 'vitest';
import { calculateOptimalBidPrice } from '../bidCalculations';
import { BidAValueItem } from '@/types/bid';

/**
 * 새 공식:
 *   estimated_price = 기초금액 * (rsrvtnPrceRngBgnRate + rsrvtnPrceRngEndRate) / 200
 *   lower_bound = ((estimated_price - A) * 낙찰하한율 / 100) + A
 *   bid_price = lower_bound * 1.001
 */

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

describe('calculateOptimalBidPrice', () => {
  describe('정상 계산', () => {
    it('새 공식으로 투찰가를 계산한다', () => {
      // A값 = 10000000+5000000+3000000+2000000+1500000+500000+1000000 = 23000000
      const aValueItem = makeAValueItem();
      const basisAmount = 1000000000;
      const minSuccessRate = 87.745;

      // estimated_price = 1000000000 * (99.855 + 103.045) / 200
      //                 = 1000000000 * 202.9 / 200 = 1014500000
      // lower_bound = ((1014500000 - 23000000) * 87.745 / 100) + 23000000
      //             = (991500000 * 0.87745) + 23000000
      //             = 869991675 + 23000000 = 892991675
      // bid_price = 892991675 * 1.001 = ceil(893884666.675) = 893884667

      const result = calculateOptimalBidPrice(basisAmount, aValueItem, minSuccessRate);

      expect(result.basisAmount).toBe(1000000000);
      expect(result.aValue).toBe(23000000);
      expect(result.minSuccessRate).toBe(87.745);
      expect(result.estimatedPrice).toBe(1014500000);
      expect(result.lowerBound).toBe(892991675);
      expect(result.bidPrice).toBe(Math.ceil(892991675 * 1.001));
    });

    it('qltyMngcst와 smkpAmt가 Y일 때 A값에 포함한다', () => {
      const aValueItem = makeAValueItem({
        qltyMngcstAObjYn: 'Y',
        qltyMngcst: '2000000',
        smkpAmtYn: 'Y',
        smkpAmt: '3000000',
      });

      const result = calculateOptimalBidPrice(1000000000, aValueItem, 87.745);

      // A값 = 23000000 + 2000000 + 3000000 = 28000000
      expect(result.aValue).toBe(28000000);
    });
  });

  describe('엣지 케이스', () => {
    it('기초금액이 0이면 모든 결과가 0이다', () => {
      const result = calculateOptimalBidPrice(0, makeAValueItem(), 87.745);

      expect(result.basisAmount).toBe(0);
      expect(result.estimatedPrice).toBe(0);
      expect(result.lowerBound).toBe(0);
      expect(result.bidPrice).toBe(0);
    });

    it('aValueItem이 null이면 A값은 0이다', () => {
      const result = calculateOptimalBidPrice(1000000000, null, 87.745);

      expect(result.aValue).toBe(0);
      // A=0이므로 lower_bound = estimated_price * 낙찰하한율 / 100
      expect(result.bidPrice).toBeGreaterThan(0);
    });

    it('rsrvtnPrceRngBgnRate/EndRate가 undefined이면 기본 범위를 사용한다', () => {
      const aValueItem = makeAValueItem({
        rsrvtnPrceRngBgnRate: undefined,
        rsrvtnPrceRngEndRate: undefined,
      });

      const result = calculateOptimalBidPrice(1000000000, aValueItem, 87.745);

      // 기본값: +-3% → bgnRate=97, endRate=103 → 평균 100% → estimated = 기초금액
      expect(result.estimatedPrice).toBe(1000000000);
    });

    it('rsrvtnPrceRngBgnRate/EndRate가 빈 문자열이면 기본 범위를 사용한다', () => {
      const aValueItem = makeAValueItem({
        rsrvtnPrceRngBgnRate: '',
        rsrvtnPrceRngEndRate: '',
      });

      const result = calculateOptimalBidPrice(1000000000, aValueItem, 87.745);

      expect(result.estimatedPrice).toBe(1000000000);
      expect(result.bidPrice).toBeGreaterThan(0);
    });

    it('낙찰하한율이 문자열로 전달되어도 정상 동작한다', () => {
      const result = calculateOptimalBidPrice(
        '1000000000' as unknown as number,
        makeAValueItem(),
        '87.745' as unknown as number
      );

      expect(result.bidPrice).toBeGreaterThan(0);
    });

    it('aValueItem이 숫자(레거시)로 전달되면 A값으로 사용한다', () => {
      const result = calculateOptimalBidPrice(1000000000, 50000000 as unknown as BidAValueItem, 87.745);

      expect(result.aValue).toBe(50000000);
    });

    it('낙찰하한율이 0이면 lowerBound는 A값과 같다', () => {
      const aValueItem = makeAValueItem();
      const result = calculateOptimalBidPrice(1000000000, aValueItem, 0);

      expect(result.lowerBound).toBe(23000000);
      expect(result.bidPrice).toBe(Math.ceil(23000000 * 1.001));
    });

    it('Infinity 입력은 fallback 값을 사용한다', () => {
      const result = calculateOptimalBidPrice(Infinity, makeAValueItem(), 87.745);

      expect(result.basisAmount).toBe(0);
      expect(result.bidPrice).toBe(0);
    });

    it('NaN 입력은 fallback 값을 사용한다', () => {
      const result = calculateOptimalBidPrice(NaN, makeAValueItem(), 87.745);

      expect(result.basisAmount).toBe(0);
      expect(result.bidPrice).toBe(0);
    });
  });
});
