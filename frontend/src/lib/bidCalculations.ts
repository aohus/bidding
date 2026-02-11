import { BidCalculationResult, BidAValueItem } from '@/types/bid';

/**
 * 나라장터 예비가격 제도:
 * - 기초금액을 기준으로 ±N% 범위에서 15개의 예비가격을 생성
 * - 참가자들이 각 2개씩 선택하여, 가장 많이 선택된 4개의 평균이 예정가격
 * - 통계적으로 예정가격은 기초금액 × (범위중앙값)에 수렴
 *
 * 최적 투찰가 = ((예정가격 - A값) × 낙찰하한율) + A값
 */
export function calculateOptimalBidPrice(
  basisAmount: number | string,
  _priceDecisionMethod: string,
  aValueItem: BidAValueItem | number | null | undefined,
  minSuccessRate: number | string
): BidCalculationResult {
  const safeBasisAmount = Number(basisAmount) || 0;
  const safeMinRate = (Number(minSuccessRate) || 0) / 100;

  // A값 계산
  let aValue = 0;
  if (aValueItem && typeof aValueItem === 'object') {
    const parse = (val: string | undefined) => parseInt(val || '0', 10) || 0;

    const defaultA =
      parse(aValueItem.sftyMngcst) +
      parse(aValueItem.sftyChckMngcst) +
      parse(aValueItem.rtrfundNon) +
      parse(aValueItem.mrfnHealthInsrprm) +
      parse(aValueItem.npnInsrprm) +
      parse(aValueItem.odsnLngtrmrcprInsrprm) +
      parse(aValueItem.envCnsrvcst);

    const qltyA = aValueItem.qltyMngcstAObjYn === 'Y' ? parse(aValueItem.qltyMngcst) : 0;
    const smkpA = aValueItem.smkpAmtYn === 'Y' ? parse(aValueItem.smkpAmt) : 0;

    aValue = defaultA + qltyA + smkpA;
  }

  // 투찰가 계산: ((기초금액 × 사정율 - A) × 하한율) + A
  const calcBidPrice = (adjRatePercent: number) => {
    const adjRate = adjRatePercent / 100;
    const predAvg = safeBasisAmount * adjRate;
    const result = Math.ceil((predAvg - aValue) * safeMinRate) + aValue;
    return isNaN(result) ? 0 : result;
  };

  // 사정율 99.5% ~ 100.2% 범위에서 3개 전략
  const strategies = [
    { label: '공격', adjRate: 99.55 },
    { label: '표준', adjRate: 99.85 },
    { label: '안정', adjRate: 100.15 },
  ];

  const recommendations = strategies.map((s) => {
    const price = calcBidPrice(s.adjRate);
    const bidRate = safeBasisAmount > 0
      ? Math.round((price / safeBasisAmount) * 10000) / 100
      : 0;
    return {
      label: s.label,
      price,
      adjRate: s.adjRate,
      bidRate,
    };
  });

  return {
    basisAmount: safeBasisAmount,
    minSuccessRate: Number(minSuccessRate) || 0,
    aValue,
    recommendations,
  };
}
