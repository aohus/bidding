import { BidCalculationResult, BidAValueItem, ReserveRateSource } from '@/types/bid';

/**
 * 적격심사제 최적 투찰가 계산 (NEW 공식)
 *
 * Step 1: aValue = 구성항목 합산
 * Step 2: lowerLimitRate = bid.sucsfbidLwltRate || 87.745
 * Step 3: expectedReserveRate (예상 사정율) — 검증 후 [MIN, MAX] 클램프, 부재 시 1.0
 * Step 4: expectedPresumedPrice (추정 예정가격) = round(basisAmount × expectedReserveRate)
 * Step 5: estimatedLowerBound = round((expectedPresumedPrice - aValue) × lowerLimitRate/100 + aValue)
 * Step 6: optimalBidPrice = estimatedLowerBound + marginWon (default 0, 음수 차단)
 * Step 7: confidenceRange — 사정율 ±RESERVE_RATE_DELTA 변동 시 낙찰하한가 범위
 */

/**
 * @deprecated default marginWon=0 으로 변경. 안전 마진 적용 시 input.marginWon 사용.
 * 기존 import 호환성을 위해 export 유지.
 */
export const FIXED_MARGIN = 1000;

const DEFAULT_RESERVE_RATE = 1.0;
const RESERVE_RATE_MIN = 0.5;
const RESERVE_RATE_MAX = 1.5;
const RESERVE_RATE_DELTA = 0.03;
const RESERVE_RATE_DECIMALS = 5;
const DEFAULT_LOWER_LIMIT_RATE = 87.745;
const DEFAULT_MARGIN_WON = 0;

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

function buildNote(marginWon: number): string {
  if (marginWon === 0) {
    return '추정 예정가격 기반 낙찰하한가 전략';
  }
  return `낙찰하한가 + ${marginWon.toLocaleString()}원 전략`;
}

function buildMargin(marginWon: number): string {
  if (marginWon === 0) {
    return '없음';
  }
  return `+${marginWon.toLocaleString()}원`;
}

function sanitizeReserveRate(value: number | undefined): number {
  if (value == null || !isFinite(value) || value <= 0) {
    return DEFAULT_RESERVE_RATE;
  }
  const clamped = Math.min(Math.max(value, RESERVE_RATE_MIN), RESERVE_RATE_MAX);
  return Number(clamped.toFixed(RESERVE_RATE_DECIMALS));
}

function sanitizeMargin(value: number | undefined): number {
  if (value == null || !isFinite(value) || value < 0) {
    return DEFAULT_MARGIN_WON;
  }
  return value;
}

interface CalcInput {
  basisAmount: string | number | undefined | null;
  fallbackBasisAmount: string | number | undefined | null;
  aValueItem: BidAValueItem | null | undefined;
  sucsfbidLwltRate: string | undefined;
  expectedReserveRate?: number;
  reserveRateSource?: ReserveRateSource;
  marginWon?: number;
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
  const lowerLimitRate = safeNum(input.sucsfbidLwltRate) ?? DEFAULT_LOWER_LIMIT_RATE;

  // Step 3: 예상 사정율 (음수/0/NaN/극단값 클램프)
  const expectedReserveRate = sanitizeReserveRate(input.expectedReserveRate);
  const reserveRateSource: ReserveRateSource =
    input.reserveRateSource ?? 'fallback_default';

  // Step 4: 추정 예정가격 = round(기초금액 × 예상 사정율)
  const expectedPresumedPrice = Math.round(basisAmount * expectedReserveRate);

  // Step 5: 추정 낙찰하한가 = round((추정 예정가격 - A값) × 낙찰하한율 + A값)
  const lowerBound = (presumedPrice: number) =>
    Math.round(((presumedPrice - aValue) * lowerLimitRate) / 100 + aValue);

  const estimatedLowerBound = lowerBound(expectedPresumedPrice);

  // Step 6: 최적 투찰금액 = 추정 낙찰하한가 + marginWon (음수 차단)
  const marginWon = sanitizeMargin(input.marginWon);
  const optimalBidPrice = estimatedLowerBound + marginWon;

  // Step 7: 신뢰 구간 — 사정율 ±RESERVE_RATE_DELTA 변동 시 낙찰하한가 범위
  // (사정율 0.97 입력 시: [0.94, 1.00] basisAmount → estimatedLowerBound가 구간 내부에 위치)
  const rateLow = Math.max(0, expectedReserveRate - RESERVE_RATE_DELTA);
  const rateHigh = expectedReserveRate + RESERVE_RATE_DELTA;
  const lbLow = lowerBound(basisAmount * rateLow);
  const lbHigh = lowerBound(basisAmount * rateHigh);

  return {
    ok: true,
    optimalBidPrice,
    estimatedLowerBound,
    confidenceRange: { low: lbLow, high: lbHigh },
    basisAmount,
    usedFallback,
    aValue,
    lowerLimitRate,
    expectedPresumedPrice,
    expectedReserveRate,
    reserveRateSource,
    margin: buildMargin(marginWon),
    note: buildNote(marginWon),
  };
}
