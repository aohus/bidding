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
  priceDecisionMethod: string,
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

  // 예비가격범위 기반 동적 사정율 계산
  const bgnRate = aValueItem && typeof aValueItem === 'object'
    ? parseFloat(aValueItem.rsrvtnPrceRngBgnRate || '0')
    : 0;
  const endRate = aValueItem && typeof aValueItem === 'object'
    ? parseFloat(aValueItem.rsrvtnPrceRngEndRate || '0')
    : 0;

  let optimalAdjRate: number;
  let recommendedAdjRate: number;
  let strategyExplanation: string;

  if (bgnRate > 0 && endRate > 0) {
    // 범위가 제공된 경우 동적 계산
    // 예: bgnRate=97, endRate=103 → 기초금액의 97%~103% 범위에서 15개 예비가격
    // 예정가격 기대값 = 기초금액 × (bgnRate + endRate) / 2 / 100
    const midRate = (bgnRate + endRate) / 200; // 비율(소수)
    const rangeWidth = (endRate - bgnRate) / 100;

    // 최적: 중앙값 기반 (통계적 기대값)
    optimalAdjRate = midRate;

    // 권장: 중앙에서 약간 위 (안전마진, 범위폭의 5% 추가)
    recommendedAdjRate = midRate + rangeWidth * 0.05;

    strategyExplanation = [
      `[투찰 전략 분석]`,
      ``,
      `예비가격범위: 기초금액의 ${bgnRate}% ~ ${endRate}%`,
      `→ 15개 예비가격이 이 범위에서 균등 생성됩니다.`,
      `→ 참가자 선택 기반 4개 평균이 예정가격이 됩니다.`,
      ``,
      `통계적 기대 사정율: ${(midRate * 100).toFixed(3)}% (범위 중앙값)`,
      `→ 4개 평균의 기대값은 전체 범위의 중앙에 수렴합니다.`,
      ``,
      `최적 투찰가: 기대 예정가격 기준 하한율 적용`,
      `→ (기초금액 × ${(optimalAdjRate * 100).toFixed(3)}% - A값) × ${minSuccessRate}% + A값`,
      ``,
      `권장 투찰가: 안전마진(범위폭 5%) 추가`,
      `→ (기초금액 × ${(recommendedAdjRate * 100).toFixed(3)}% - A값) × ${minSuccessRate}% + A값`,
    ].join('\n');
  } else {
    // 범위 미제공 시 통계적 기본값 사용
    // 일반적으로 ±2% 범위 → 중앙값 100%
    // 약간의 상향 보정 (100.152%)
    optimalAdjRate = 1.00152;
    recommendedAdjRate = 1.00185;

    strategyExplanation = [
      `[투찰 전략 분석]`,
      ``,
      `예비가격범위 정보가 제공되지 않아 통계적 기본값을 사용합니다.`,
      `(일반 공사 기준 ±2% 범위 가정)`,
      ``,
      `최적 사정율: ${(optimalAdjRate * 100).toFixed(3)}%`,
      `권장 사정율: ${(recommendedAdjRate * 100).toFixed(3)}%`,
      ``,
      `※ A값 상세정보가 제공되면 더 정확한 분석이 가능합니다.`,
    ].join('\n');
  }

  const floorAdjRate = 1.00000;

  // 투찰가 계산: ((예정가격 - A) × 하한율) + A
  const calcBidPrice = (adjRate: number) => {
    const predAvg = safeBasisAmount * adjRate;
    const result = Math.ceil((predAvg - aValue) * safeMinRate) + aValue;
    return isNaN(result) ? 0 : result;
  };

  const minPrice = calcBidPrice(floorAdjRate);
  const optimalPrice = calcBidPrice(optimalAdjRate);
  const recommendedPrice = calcBidPrice(recommendedAdjRate);

  // A값 세부내역
  let aValueDetail = '';
  if (aValue && typeof aValueItem === 'object') {
    const parseStr = (val: string | undefined) => parseInt(val || '0', 10).toLocaleString();
    aValueDetail = [
      `[A값 산출 내역]`,
      `- 국민연금: ${parseStr(aValueItem.npnInsrprm)}원`,
      `- 건강보험: ${parseStr(aValueItem.mrfnHealthInsrprm)}원`,
      `- 요양보험: ${parseStr(aValueItem.odsnLngtrmrcprInsrprm)}원`,
      `- 산업안전보건비: ${parseStr(aValueItem.sftyMngcst)}원`,
      `- 퇴직공제부금: ${parseStr(aValueItem.rtrfundNon)}원`,
      `- 안전관리비: ${parseStr(aValueItem.sftyChckMngcst)}원`,
      `- 환경보전비: ${parseStr(aValueItem.envCnsrvcst)}원`,
      `- 품질관리비: ${aValueItem.qltyMngcstAObjYn === 'Y' ? parseStr(aValueItem.qltyMngcst) : '0(미대상)'}원`,
      `- 표준시장단가: ${aValueItem.smkpAmtYn === 'Y' ? parseStr(aValueItem.smkpAmt) : '0(미대상)'}원`,
      `--------------------------------`,
      `최종 합계(A값): ${aValue.toLocaleString()}원`,
    ].join('\n');
  }

  const calculation = [
    `[산출 금액]`,
    `- 기초금액(bssamt): ${safeBasisAmount.toLocaleString()}원`,
    `- 낙찰하한율: ${minSuccessRate}%`,
    ``,
    `1. 최저 투찰가 (사정율 100%): ${minPrice.toLocaleString()}원`,
    `2. 최적 투찰가 (사정율 ${(optimalAdjRate * 100).toFixed(3)}%): ${optimalPrice.toLocaleString()}원`,
    `3. 권장 투찰가 (사정율 ${(recommendedAdjRate * 100).toFixed(3)}%): ${recommendedPrice.toLocaleString()}원`,
    ``,
    aValue > 0 ? aValueDetail : '※ 적용된 A값이 없습니다 (0원).',
    ``,
    `※ 예정가격 결정방법: ${priceDecisionMethod}`,
    `※ 원단위 미만은 안전을 위해 올림 처리되었습니다.`,
    ``,
    strategyExplanation,
  ].join('\n');

  return {
    optimalPrice,
    minPrice,
    recommendedPrice,
    calculation,
    aValueDetail,
  };
}
