import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 적격심사제 최적 투찰가 계산 (S1 전략)
 *
 * 사정율: 지역범위 × 면허유형 × 금액범위 통계 기반 lookup table 사용
 *
 * Step 1: assessmentRate = RATE_TABLE[regionScope][licenseGroup][amountRange]
 * Step 2: estimatedPrice = basisAmount × assessmentRate / 100
 * Step 3: aValue = 구성항목 합산
 * Step 4: lowerLimitRate = bid.sucsfbidLwltRate || 87.745
 * Step 5: estimatedLowerBound = ((estimatedPrice - aValue) × lowerLimitRate/100) + aValue
 * Step 6: optimalBidPrice = ceil(estimatedLowerBound × MARGIN)
 * Step 7: confidenceRange — 예비가격 ±3% 범위 기반
 */

const MARGIN = 1.001;
const RANGE_LOW_PCT = 97;
const RANGE_HIGH_PCT = 103;

export type RegionScope = 'province' | 'city';
export type LicenseGroup = 'general' | 'landscaping';
export type AmountRange = 'under1' | 'from1to3' | 'over3';

// 통계 기반 최적 사정율 lookup table
// regionScope → licenseGroup → amountRange → rate (%)
const RATE_TABLE: Record<RegionScope, Partial<Record<LicenseGroup, Partial<Record<AmountRange, number>>>>> = {
  province: {
    general: { under1: 99.930, from1to3: 100.092, over3: 100.140 },
    landscaping: { under1: 99.321, from1to3: 99.822, over3: 99.502 },
  },
  city: {
    general: { under1: 99.536, from1to3: 99.994 },
  },
};

function safeNum(value: string | number | undefined | null): number | null {
  if (value == null || value === '') return null;
  const n = Number(value);
  return isFinite(n) ? n : null;
}

/**
 * 참가가능지역에서 지역 범위 결정.
 * - 콤마(여러 지역) → province (광역)
 * - 단일 지역에 시/군/구 포함 → city
 * - 그 외 → province
 */
export function determineRegionScope(prtcptPsblRgnNms: string | undefined): RegionScope {
  if (!prtcptPsblRgnNms) return 'province';
  if (prtcptPsblRgnNms.includes(',')) return 'province';
  const trimmed = prtcptPsblRgnNms.trim();
  if (/\s+\S+(시|군|구)$/.test(trimmed)) return 'city';
  return 'province';
}

/**
 * 허용업종에서 면허 유형 결정.
 * - 조경식재 또는 나무병원 포함 → landscaping
 * - 그 외 → general (전체면허)
 */
export function determineLicenseGroup(permsnIndstrytyListNms: string | undefined): LicenseGroup {
  if (!permsnIndstrytyListNms) return 'general';
  if (permsnIndstrytyListNms.includes('조경식재') || permsnIndstrytyListNms.includes('나무병원')) {
    return 'landscaping';
  }
  return 'general';
}

/**
 * 기초금액에서 금액 범위 결정.
 * - 1억 미만 → under1
 * - 1~3억 → from1to3
 * - 3억 이상 → over3
 */
export function determineAmountRange(amount: number): AmountRange {
  if (amount < 100_000_000) return 'under1';
  if (amount < 300_000_000) return 'from1to3';
  return 'over3';
}

/**
 * 사정율 lookup (fallback 포함)
 * 1. 정확한 매칭 시도
 * 2. province + 동일 면허로 fallback
 * 3. 동일 지역 + general 면허로 fallback
 * 4. province + general fallback
 * 5. 최종 기본값 100.0
 */
function getOptimalAssessmentRate(
  regionScope: RegionScope,
  licenseGroup: LicenseGroup,
  amountRange: AmountRange,
): number {
  const rate = RATE_TABLE[regionScope]?.[licenseGroup]?.[amountRange];
  if (rate != null) return rate;

  if (regionScope !== 'province') {
    const provinceRate = RATE_TABLE.province?.[licenseGroup]?.[amountRange];
    if (provinceRate != null) return provinceRate;
  }

  if (licenseGroup !== 'general') {
    const generalRate = RATE_TABLE[regionScope]?.general?.[amountRange];
    if (generalRate != null) return generalRate;
  }

  const defaultRate = RATE_TABLE.province?.general?.[amountRange];
  if (defaultRate != null) return defaultRate;

  return 100.0;
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
  prtcptPsblRgnNms?: string;
  permsnIndstrytyListNms?: string;
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

  // Step 1: 사정율 lookup (지역범위 × 면허유형 × 금액범위)
  const regionScope = determineRegionScope(input.prtcptPsblRgnNms);
  const licenseGroup = determineLicenseGroup(input.permsnIndstrytyListNms);
  const amountRange = determineAmountRange(basisAmount);
  const assessmentRate = getOptimalAssessmentRate(regionScope, licenseGroup, amountRange);
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
    margin: '0.01%',
    note: '낙찰하한가 +0.01% 전략',
  };
}
