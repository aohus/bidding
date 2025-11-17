import { BidCalculationResult } from '@/types/bid';

export function calculateOptimalBidPrice(
  estimatedPrice: number,
  priceDecisionMethod: string,
  minSuccessRate: number
): BidCalculationResult {
  // 낙찰하한율을 퍼센트로 변환 (예: 87.745 -> 0.87745)
  const minRate = minSuccessRate / 100;
  
  // 최저가격 = 추정가격 × 낙찰하한율
  const minPrice = Math.floor(estimatedPrice * minRate);
  
  // 최고가격 = 추정가격 (100%)
  const maxPrice = estimatedPrice;
  
  // 표준 공식: 낙찰하한율 + (100% - 낙찰하한율) × 0.3~0.5 범위의 랜덤값
  // 안전한 범위로 40% 지점 선택
  const safetyFactor = 0.4;
  const recommendedRate = minRate + (1 - minRate) * safetyFactor;
  const recommendedPrice = Math.floor(estimatedPrice * recommendedRate);
  
  // 최적가격: 88-92% 범위 (보수적 접근)
  const optimalRate = 0.90; // 90%
  const optimalPrice = Math.floor(estimatedPrice * optimalRate);
  
  const calculation = `
계산 방식:
- 추정가격: ${estimatedPrice.toLocaleString()}원
- 낙찰하한율: ${minSuccessRate}%
- 최저가격: ${minPrice.toLocaleString()}원 (추정가격 × ${minSuccessRate}%)
- 최고가격: ${maxPrice.toLocaleString()}원 (추정가격 × 100%)
- 권장가격: ${recommendedPrice.toLocaleString()}원 (추정가격 × ${(recommendedRate * 100).toFixed(2)}%)
- 최적가격: ${optimalPrice.toLocaleString()}원 (추정가격 × 90%)

※ 표준 공식: 낙찰하한율 + (100% - 낙찰하한율) × 안전계수(0.4)
※ 예정가격결정방법: ${priceDecisionMethod}
  `.trim();

  return {
    optimalPrice,
    minPrice,
    maxPrice,
    recommendedPrice,
    calculation
  };
}