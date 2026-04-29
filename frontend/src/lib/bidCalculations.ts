import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 적격심사제 최적 투찰가 계산
 *
 * Step 1: aValue = 구성항목 합산
 * Step 2: lowerLimitRate = bid.sucsfbidLwltRate || 87.745
 * Step 3: estimatedLowerBound = ((basisAmount - aValue) × lowerLimitRate/100) + aValue
 * Step 4: optimalBidPrice = estimatedLowerBound + FIXED_MARGIN
 * Step 5: confidenceRange — 기초금액 ±3% 범위 기반
 */

export const FIXED_MARGIN = 1000;
const RANGE_LOW_PCT = 97;
const RANGE_HIGH_PCT = 103;

function safeNum(value: string | number | undefined | null): number | null {
  if (value == null || value === '') return null;
  const n = Number(value);
  return isFinite(n) ? n : null;
}

function parseA(aValueItem: BidAValueItem): number {
  const p = (val: string | undefined) => safeNum(val) ?? 0;

  const baseA =
    p(aValueItem.sftyMngcst) +
    p(aValueItem.sftyChckMngcst) +
    p(aValueItem.rtrfundNon) +
    p(aValueItem.mrfnHealthInsrprm) +
    p(aValueItem.npnInsrprm) +
    p(aValueItem.odsnLngtrmrcprInsrprm) +
    p(aValueItem.envCnsrvcst);

  const qltyA = aValueItem.qltyMngcstAObjYn === 'Y' ? p(aValueItem.qltyMngcst) : 0;
  const smkpA = aValueItem.smkpAmtYn === 'Y' ? p(aValueItem.smkpAmt) : 0;

  return baseA + qltyA + smkpA;
}

interface CalcInput {
  basisAmount: string | number | undefined | null;
  fallbackBasisAmount: string | number | undefined | null;
  aValueItem: BidAValueItem | null | undefined;
  sucsfbidLwltRate: string | undefined;
}

export function calculateOptimalBidPrice(input: CalcInput): BidCalculationResult {
  // Step 0: basisAmount 검증 (없으면 배정예산금액 fallback)
  const rawBasis = safeNum(input.basisAmount);
  const fallbackBasis = safeNum(input.fallbackBasisAmount);
  const usedFallback = (rawBasis == null || rawBasis <= 0) && fallbackBasis != null && fallbackBasis > 0;
  const basisAmount = (rawBasis != null && rawBasis > 0) ? rawBasis : fallbackBasis;
  if (basisAmount == null || basisAmount <= 0) {
    return { ok: false, error: '기초금액을 확인할 수 없습니다. 공고 원문을 확인하세요.' };
  }

  // Step 1: A값
  const aValue = input.aValueItem ? parseA(input.aValueItem) : 0;

  // Step 2: 낙찰하한율
  const lowerLimitRate = safeNum(input.sucsfbidLwltRate) ?? 87.745;

  // Step 3: 추정 낙찰하한가 = (기초금액 - A값) × 낙찰하한율 + A값
  const lowerBound = (basis: number) =>
    Math.round(((basis - aValue) * lowerLimitRate) / 100 + aValue);

  const estimatedLowerBound = lowerBound(basisAmount);

  // Step 4: 최적 투찰금액 = 추정 낙찰하한가 + 1,000원
  const optimalBidPrice = estimatedLowerBound + FIXED_MARGIN;

  // Step 5: 신뢰 구간 (기초금액 ±3% 범위 기반)
  const lbLow = lowerBound((basisAmount * RANGE_LOW_PCT) / 100);
  const lbHigh = lowerBound((basisAmount * RANGE_HIGH_PCT) / 100);

  return {
    ok: true,
    optimalBidPrice,
    estimatedLowerBound,
    confidenceRange: { low: lbLow, high: lbHigh },
    basisAmount,
    usedFallback,
    aValue,
    lowerLimitRate,
    margin: '+1,000원',
    note: '낙찰하한가 + 1,000원 전략',
  };
}
