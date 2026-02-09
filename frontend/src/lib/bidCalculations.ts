import { BidCalculationResult, BidAValueItem } from '@/types/bid';

export function calculateOptimalBidPrice(
  basisAmount: number | string,
  priceDecisionMethod: string,
  aValueItem: BidAValueItem | number | null | undefined,
  minSuccessRate: number | string
): BidCalculationResult {
  // 1. 기초 데이터 숫자 변환 (안전장치)
  // bssamt(기초금액)을 기준으로 계산합니다.
  const safeBasisAmount = Number(basisAmount) || 0;
  const safeMinRate = (Number(minSuccessRate) || 0) / 100;

  let aValue = 0;
  if (aValueItem && typeof aValueItem === 'object') {
      // [핵심] basePrceAamt가 없거나 null이면 각 항목 수동 합산
      const parse = (val: string | undefined) => parseInt(val || '0', 10) || 0;

      // 무조건 더하는 항목들
      const defaultA = 
        parse(aValueItem.sftyMngcst) +           // 산업안전보건관리비
        parse(aValueItem.sftyChckMngcst) +      // 안전관리비
        parse(aValueItem.rtrfundNon) +          // 퇴직공제부금비
        parse(aValueItem.mrfnHealthInsrprm) +    // 국민건강보험료
        parse(aValueItem.npnInsrprm) +          // 국민연금보험료
        parse(aValueItem.odsnLngtrmrcprInsrprm) + // 노인장기요양보험료
        parse(aValueItem.envCnsrvcst);          // 환경보전비 (새로 추가)

      // 조건부 더하는 항목들
      const qltyA = aValueItem.qltyMngcstAObjYn === 'Y' ? parse(aValueItem.qltyMngcst) : 0;
      const smkpA = aValueItem.smkpAmtYn === 'Y' ? parse(aValueItem.smkpAmt) : 0;

      aValue = defaultA + qltyA + smkpA;
  }

  // 3. 전략적 사정율 설정
  const optimalAdjRate = 1.00152; 
  const recommendedAdjRate = 1.00185;
  const floorAdjRate = 1.00000;

  // 4. 예정가격 및 투찰가 계산 (A값 공식 적용)
  // 공식: ((예정가격 - A) * 하한율) + A
  // 예정가격(predAvg)은 기초금액(safeBasisAmount) * 사정율(adjRate)로 계산됩니다.
  const calcBidPrice = (adjRate: number) => {
    const predAvg = safeBasisAmount * adjRate;
    const result = Math.ceil((predAvg - aValue) * safeMinRate) + aValue;
    return isNaN(result) ? 0 : result;
  };

  const minPrice = calcBidPrice(floorAdjRate);
  const optimalPrice = calcBidPrice(optimalAdjRate);
  const recommendedPrice = calcBidPrice(recommendedAdjRate);

  // 5. 산출 근거 텍스트 생성
  let aValueDetail = '';
  if (aValue && typeof aValueItem === 'object') {
    const parseStr = (val: string | undefined) => parseInt(val || '0', 10).toLocaleString();
    aValueDetail = `
    [A값 산출 내역]
    - 국민연금: ${parseStr(aValueItem.npnInsrprm)}원
    - 건강보험: ${parseStr(aValueItem.mrfnHealthInsrprm)}원
    - 요양보험: ${parseStr(aValueItem.odsnLngtrmrcprInsrprm)}원
    - 산업안전보건비: ${parseStr(aValueItem.sftyMngcst)}원
    - 퇴직공제부금: ${parseStr(aValueItem.rtrfundNon)}원
    - 안전관리비: ${parseStr(aValueItem.sftyChckMngcst)}원
    - 환경보전비: ${parseStr(aValueItem.envCnsrvcst)}원
    - 품질관리비: ${aValueItem.qltyMngcstAObjYn === 'Y' ? parseStr(aValueItem.qltyMngcst) : '0(미대상)'}원
    - 표준시장단가: ${aValueItem.smkpAmtYn === 'Y' ? parseStr(aValueItem.smkpAmt) : '0(미대상)'}원
    --------------------------------
    최종 합계(A값): ${aValue.toLocaleString()}원
        `.trim();
      }

      const calculation = `
    [나라장터 정밀 투찰 결과]
    - 기초금액(bssamt): ${safeBasisAmount.toLocaleString()}원
    - 낙찰하한율: ${minSuccessRate}%

    [산출 금액]
    1. 최저 투찰가 (사정율 100%): ${minPrice.toLocaleString()}원
    2. 최적 투찰가 (예측 사정율 ${(optimalAdjRate * 100).toFixed(3)}%): ${optimalPrice.toLocaleString()}원
    3. 권장 투찰가 (예측 사정율 ${(recommendedAdjRate * 100).toFixed(3)}%): ${recommendedPrice.toLocaleString()}원
    
    ${aValue > 0 ? aValueDetail : '※ 적용된 A값이 없습니다 (0원).'}

    ※ 예정가격 결정방법: ${priceDecisionMethod}
    ※ 원단위 미만은 안전을 위해 올림 처리되었습니다.
      `.trim();

  return {
    optimalPrice,
    minPrice,
    recommendedPrice,
    calculation,
    aValueDetail
  };
}

  return {
    optimalPrice,
    minPrice,
    recommendedPrice,
    calculation,
    aValueDetail
  };
}