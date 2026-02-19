import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 적격심사제 최적 투찰가 계산 (S1 전략)
 *
 * 배경: 낙찰하한가 이상 최저 투찰금액이 낙찰.
 *       추정 낙찰하한가 × 1.001 (0.1% 마진)이 최적.
 *
 * Step 1: estimatedPrice = basisAmount × (bgnRate + endRate) / 200
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
  bgnRate: string | undefined;
  endRate: string | undefined;
  aValueItem: BidAValueItem | null | undefined;
  sucsfbidLwltRate: string | undefined;
}

export function calculateOptimalBidPrice(input: CalcInput): BidCalculationResult {
  // Step 0: basisAmount 검증 (fallback 금지)
  const basisAmount = safeNum(input.basisAmount);
  if (basisAmount == null || basisAmount <= 0) {
    return { ok: false, error: '기초금액을 확인할 수 없습니다. 공고 원문을 확인하세요.' };
  }

  // Step 0: bgnRate / endRate 검증 (fallback 금지)
  const bgnRate = safeNum(input.bgnRate);
  const endRate = safeNum(input.endRate);
  if (bgnRate == null || endRate == null || bgnRate <= 0 || endRate <= 0) {
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
    aValue,
    lowerLimitRate,
    margin: '0.1%',
    note: '낙찰하한가 +0.1% 전략',
  };
}
