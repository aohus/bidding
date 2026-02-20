import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 적격심사제 최적 투찰가 계산 (S1 전략)
 *
 * 배경: 낙찰하한가 이상 최저 투찰금액이 낙찰.
 *       추정 낙찰하한가 × 1.001 (0.1% 마진)이 최적.
 *
 * 나라장터 API는 예비가격범위율을 상대값(오프셋)으로 반환:
 *   공사: bgnRate=-3, endRate=+3  → 절대값 97%, 103%
 *   용역: bgnRate=-2, endRate=+2  → 절대값 98%, 102%
 *
 * Step 1: estimatedPrice = basisAmount × (absBgnRate + absEndRate) / 200
 * Step 2: aValue = 구성항목 합산
 * Step 3: lowerLimitRate = bid.sucsfbidLwltRate || 87.745
 * Step 4: estimatedLowerBound = ((estimatedPrice - aValue) × lowerLimitRate/100) + aValue
 * Step 5: optimalBidPrice = ceil(estimatedLowerBound × 1.001)
 * Step 6: confidenceRange = { low: lbLow, high: lbHigh }
 */

const MARGIN = 1.001;

function safeNum(value: string | number | undefined | null): number | null {
  if (value == null || value === '') return null;
  const n = Number(value);
  return isFinite(n) ? n : null;
}

/**
 * API 예비가격범위율을 절대값(%)으로 변환.
 * API는 상대값(-3, +3)을 반환하지만, 절대값(97, 103)으로 전달될 수도 있음.
 * |rate| <= 50이면 상대값으로 판단하여 100을 더함.
 */
function toAbsoluteRate(rate: number): number {
  return Math.abs(rate) <= 50 ? 100 + rate : rate;
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
  bgnRate: string | undefined;
  endRate: string | undefined;
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

  // Step 0: bgnRate / endRate 검증 (fallback 금지)
  const rawBgnRate = safeNum(input.bgnRate);
  const rawEndRate = safeNum(input.endRate);
  if (rawBgnRate == null || rawEndRate == null) {
    return { ok: false, error: '예비가격 범위를 확인할 수 없습니다. 공고 원문에서 확인 후 수동 입력하세요.' };
  }

  // 상대값(-3, +3) → 절대값(97, 103) 변환
  const bgnRate = toAbsoluteRate(rawBgnRate);
  const endRate = toAbsoluteRate(rawEndRate);
  if (bgnRate <= 0 || endRate <= 0) {
    return { ok: false, error: '예비가격 범위를 확인할 수 없습니다. 공고 원문에서 확인 후 수동 입력하세요.' };
  }

  // Step 1: 예정가격 추정
  const estimatedPrice = Math.round(basisAmount * (bgnRate + endRate) / 200);

  // Step 2: A값
  const aValue = input.aValueItem ? parseA(input.aValueItem) : 0;

  // Step 3: 낙찰하한율
  const lowerLimitRate = safeNum(input.sucsfbidLwltRate) ?? 87.745;

  // Step 4: 추정 낙찰하한가
  const estimatedLowerBound = Math.ceil(
    ((estimatedPrice - aValue) * lowerLimitRate / 100) + aValue
  );

  // Step 5: 최적 투찰금액
  const optimalBidPrice = Math.ceil(estimatedLowerBound * MARGIN);

  // Step 6: 신뢰 구간
  const lbLow = Math.ceil(
    ((basisAmount * bgnRate / 100 - aValue) * lowerLimitRate / 100) + aValue
  );
  const lbHigh = Math.ceil(
    ((basisAmount * endRate / 100 - aValue) * lowerLimitRate / 100) + aValue
  );

  return {
    ok: true,
    optimalBidPrice,
    estimatedLowerBound,
    estimatedPrice,
    confidenceRange: { low: lbLow, high: lbHigh },
    basisAmount,
    usedFallback,
    aValue,
    lowerLimitRate,
    margin: '0.1%',
    note: '낙찰하한가 +0.1% 전략',
  };
}
