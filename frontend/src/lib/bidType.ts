import { BidItem } from '@/types/bid';

export type BidType = 'cnstwk' | 'servc';

/**
 * 공고 유형(공사/용역) 추정. 공사 공고만 주공종명·공사현장지역명을 가지므로
 * 둘 중 하나라도 있으면 공사(cnstwk), 아니면 용역(servc)으로 본다.
 */
export function inferBidType(bid: Pick<BidItem, 'mainCnsttyNm' | 'cnstrtsiteRgnNm'>): BidType {
  return bid.mainCnsttyNm || bid.cnstrtsiteRgnNm ? 'cnstwk' : 'servc';
}
