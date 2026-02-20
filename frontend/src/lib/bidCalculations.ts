import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 적격심사제 최적 투찰가 계산 (S1 전략)
 *
 * 배경: 낙찰하한가 이상 최저 투찰금액이 낙찰.
 *       추정 낙찰하한가 × 1.001 (0.1% 마진)이 최적.
 *
 * 사정율: ±3%(공사) → 99.7%, ±2%(용역) → 99.9%
 *
 * Step 1: estimatedPrice = basisAmount × 사정율 / 100
 * Step 2: aValue = 구성항목 합산
 * Step 3: lowerLimitRate = bid.sucsfbidLwltRate || 87.745
 * Step 4: estimatedLowerBound = ((estimatedPrice - aValue) × lowerLimitRate/100) + aValue
 * Step 5: optimalBidPrice = ceil(estimatedLowerBound × 1.001)
 * Step 6: confidenceRange — 고정 ±3% 범위 기반
 */

const MARGIN = 1.001;
const RANGE_LOW_PCT = 97;   // 예비가격 하한 (기초금액의 97%)
const RANGE_HIGH_PCT = 103;  // 예비가격 상한 (기초금액의 103%)

// 사정율: 예비가격 범위에 따라 결정 (통계적 수렴값)
const ASSESSMENT_RATE_3 = 99.7;  // ±3% 범위 (공사)
const ASSESSMENT_RATE_2 = 99.9;  // ±2% 범위 (용역)

function safeNum(value: string | number | undefined | null): number | null {
  if (value == null || value === '') return null;
  const n = Number(value);
  return isFinite(n) ? n : null;
}

/**
 * 예비가격범위율(endRate)로 사정율 결정.
 * |endRate| ≈ 2 → 99.9 (용역), 그 외 → 99.7 (공사 기본값)
 */
function getAssessmentRate(endRate: string | undefined): number {
  const val = safeNum(endRate);
  if (val == null) return ASSESSMENT_RATE_3;
  const abs = Math.abs(val) <= 50 ? Math.abs(val) : Math.abs(val - 100);
  return abs <= 2 ? ASSESSMENT_RATE_2 : ASSESSMENT_RATE_3;
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
  priceRangeEndRate: string | undefined;
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

  // Step 1: 사정율로 예정가격 추정
  const assessmentRate = getAssessmentRate(input.priceRangeEndRate);
  const estimatedPrice = Math.round(basisAmount * assessmentRate / 100);

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

  // Step 6: 신뢰 구간 (예비가격 ±3% 범위 기반)
  const lbLow = Math.ceil(
    ((basisAmount * RANGE_LOW_PCT / 100 - aValue) * lowerLimitRate / 100) + aValue
  );
  const lbHigh = Math.ceil(
    ((basisAmount * RANGE_HIGH_PCT / 100 - aValue) * lowerLimitRate / 100) + aValue
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
    assessmentRate,
    lowerLimitRate,
    margin: '0.1%',
    note: '낙찰하한가 +0.1% 전략',
  };
}
