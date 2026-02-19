import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 투찰 추천가 계산:
 *   estimated_price = 기초금액 × (예비가격범위시작률 + 예비가격범위종료률) / 200
 *   lower_bound = ((estimated_price - A값) × 낙찰하한율 / 100) + A값
 *   bid_price = lower_bound × 1.001
 *
 * A값은 basePrceAamt 대신 구성항목 합산으로 직접 산출합니다.
 * (투명성 확보 및 조건부 항목 제어를 위함)
 */

const DEFAULT_BGN_RATE = 97;
const DEFAULT_END_RATE = 103;
const BID_PRICE_MARGIN = 1.001;

function safeNum(value: string | number | undefined, fallback: number): number {
  if (value == null) return fallback;
  const n = Number(value);
  return isFinite(n) ? n : fallback;
}

function parseA(aValueItem: BidAValueItem): number {
  const parse = (val: string | undefined) => safeNum(val, 0);

  const baseA =
    parse(aValueItem.sftyMngcst) +
    parse(aValueItem.sftyChckMngcst) +
    parse(aValueItem.rtrfundNon) +
    parse(aValueItem.mrfnHealthInsrprm) +
    parse(aValueItem.npnInsrprm) +
    parse(aValueItem.odsnLngtrmrcprInsrprm) +
    parse(aValueItem.envCnsrvcst);

  const qltyA = aValueItem.qltyMngcstAObjYn === 'Y' ? parse(aValueItem.qltyMngcst) : 0;
  const smkpA = aValueItem.smkpAmtYn === 'Y' ? parse(aValueItem.smkpAmt) : 0;

  return baseA + qltyA + smkpA;
}

export function calculateOptimalBidPrice(
  basisAmount: number | string,
  aValueItem: BidAValueItem | number | null | undefined,
  minSuccessRate: number | string,
): BidCalculationResult {
  const safeBasisAmount = safeNum(basisAmount, 0);
  const safeMinRate = safeNum(minSuccessRate, 0);

  let aValue = 0;
  let bgnRate = DEFAULT_BGN_RATE;
  let endRate = DEFAULT_END_RATE;

  if (aValueItem && typeof aValueItem === 'object') {
    aValue = parseA(aValueItem);
    bgnRate = safeNum(aValueItem.rsrvtnPrceRngBgnRate, DEFAULT_BGN_RATE);
    endRate = safeNum(aValueItem.rsrvtnPrceRngEndRate, DEFAULT_END_RATE);
  } else if (typeof aValueItem === 'number' && isFinite(aValueItem)) {
    aValue = aValueItem;
  }

  if (safeBasisAmount === 0) {
    return {
      basisAmount: 0,
      minSuccessRate: safeMinRate,
      aValue,
      estimatedPrice: 0,
      lowerBound: 0,
      bidPrice: 0,
    };
  }

  const estimatedPrice = Math.round(safeBasisAmount * (bgnRate + endRate) / 200);
  const lowerBound = Math.ceil(((estimatedPrice - aValue) * safeMinRate / 100) + aValue);
  const bidPrice = Math.ceil(lowerBound * BID_PRICE_MARGIN);

  return {
    basisAmount: safeBasisAmount,
    minSuccessRate: safeMinRate,
    aValue,
    estimatedPrice,
    lowerBound,
    bidPrice,
  };
}
