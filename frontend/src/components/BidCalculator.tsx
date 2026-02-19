import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidAValueItem, BidItem } from '@/types/bid';
import { calculateOptimalBidPrice } from '@/lib/bidCalculations';
import { downloadDocument } from '@/lib/api';
import { backendApi } from '@/lib/backendApi';
import { Download, FileText, Calculator, ExternalLink, Info, Star, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';


interface BidCalculatorProps {
  bid: BidItem | null;
  aValueItem: BidAValueItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function BidCalculator({ bid, aValueItem, isOpen, onClose }: BidCalculatorProps) {
  const [showBidPriceInput, setShowBidPriceInput] = useState(false);
  const [bidPriceInput, setBidPriceInput] = useState('');
  const [bookmarkSaving, setBookmarkSaving] = useState(false);

  const handleSaveBookmark = async (status: 'interested' | 'bid_completed', bidPrice?: number) => {
    if (!bid) return;
    try {
      setBookmarkSaving(true);
      await backendApi.createBookmark(bid.bidNtceNo, bid.bidNtceNm, {
        status,
        bid_price: bidPrice,
        bid_notice_ord: bid.bidNtceOrd,
      });
      toast.success(status === 'interested' ? '관심공고로 저장했습니다' : '투찰완료로 저장했습니다');
      setShowBidPriceInput(false);
      setBidPriceInput('');
    } catch (error: any) {
      if (error.message?.includes('already exists')) {
        toast.error('이미 저장된 공고입니다');
      } else {
        toast.error('저장에 실패했습니다');
      }
    } finally {
      setBookmarkSaving(false);
    }
  };

  const handleBidCompletedWithPrice = () => {
    const price = parseInt(bidPriceInput.replace(/,/g, ''), 10);
    if (!price || price <= 0) {
      toast.error('투찰가를 입력해주세요');
      return;
    }
    handleSaveBookmark('bid_completed', price);
  };

  const handleBidCompletedWithoutPrice = () => {
    handleSaveBookmark('bid_completed');
  };

  if (!bid) return null;

  const basisAmount = aValueItem?.bssamt ? parseFloat(aValueItem.bssamt) : parseFloat(bid.bdgtAmt || '0');
  const minSuccessRate = parseFloat(bid.sucsfbidLwltRate || '87.745');

  const result = calculateOptimalBidPrice(basisAmount, aValueItem, minSuccessRate);

  const formatPrice = (price: string | undefined) => {
    const num = parseFloat(price || '0');
    return num.toLocaleString();
  };

  const documents = [
    { url: bid.ntceSpecDocUrl1, name: bid.ntceSpecFileNm1 || '공고규격서 1' },
    { url: bid.ntceSpecDocUrl2, name: bid.ntceSpecFileNm2 || '공고규격서 2' },
    { url: bid.ntceSpecDocUrl3, name: bid.ntceSpecFileNm3 || '공고규격서 3' },
    { url: bid.ntceSpecDocUrl4, name: bid.ntceSpecFileNm4 || '공고규격서 4' },
    { url: bid.ntceSpecDocUrl5, name: bid.ntceSpecFileNm5 || '공고규격서 5' },
    { url: bid.sptDscrptDocUrl1, name: bid.sptDscrptFileNm1 || '현장설명서 1' },
    { url: bid.sptDscrptDocUrl2, name: bid.sptDscrptFileNm2 || '현장설명서 2' },
    { url: bid.sptDscrptDocUrl3, name: bid.sptDscrptFileNm3 || '현장설명서 3' },
  ].filter((doc) => doc.url);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-blue-600" />
            <DialogTitle>공고 상세 및 투찰가 분석</DialogTitle>
          </div>
          <DialogDescription className="font-semibold text-gray-700">
            {bid.bidNtceNm}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* 0. 입찰공고 페이지 링크 - 최상단 배치 */}
          {bid.bidNtceDtlUrl && (
            <a
              href={bid.bidNtceDtlUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
            >
              <ExternalLink className="h-5 w-5 text-blue-600 shrink-0" />
              <p className="text-sm font-semibold text-blue-800">나라장터 입찰공고 페이지 바로가기</p>
            </a>
          )}

          {/* 1. 공고 기본 정보 */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-md flex items-center gap-2">
                <Info className="h-4 w-4" />
                공고 기본 정보
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">공고번호</span>
                  <span className="font-medium">{bid.bidNtceNo}-{bid.bidNtceOrd}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">공고기관</span>
                  <span className="font-medium">{bid.ntceInsttNm}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">수요기관</span>
                  <span className="font-medium">{bid.dminsttNm || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">입찰방식</span>
                  <span className="font-medium">{bid.bidMethdNm || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">계약체결방법</span>
                  <span className="font-medium">{bid.cntrctCnclsMthdNm || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">주공종명</span>
                  <span className="font-medium">{bid.mainCnsttyNm || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">입찰마감</span>
                  <span className="font-medium">{bid.bidClseDt || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">개찰일시</span>
                  <span className="font-medium">{bid.opengDt || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">예산금액</span>
                  <span className="font-medium">{formatPrice(bid.bdgtAmt)}원</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">추정가격</span>
                  <span className="font-medium">{formatPrice(bid.presmptPrce)}원</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">낙찰하한율</span>
                  <span className="font-medium">{minSuccessRate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">예정가격 결정방식</span>
                  <span className="font-medium">{bid.prearngPrceDcsnMthdNm || '-'}</span>
                </div>
                <div className="col-span-2 flex justify-between">
                  <span className="text-muted-foreground shrink-0">낙찰방법</span>
                  <span className="font-medium text-right max-w-[70%] truncate" title={bid.sucsfbidMthdNm || '-'}>{bid.sucsfbidMthdNm || '-'}</span>
                </div>
                {bid.prtcptPsblRgnNms && (
                  <div className="col-span-2 flex justify-between">
                    <span className="text-muted-foreground">참가가능지역</span>
                    <span className="font-medium text-right max-w-[70%]">{bid.prtcptPsblRgnNms}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 2. 입찰 서류 목록 */}
          {documents.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-gray-500 px-1">입찰 관련 서류</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {documents.map((doc, index) => (
                  <Button
                    key={index}
                    variant="secondary"
                    className="h-10 text-xs justify-start bg-gray-100 hover:bg-gray-200"
                    onClick={() => downloadDocument(doc.url!, doc.name)}
                  >
                    <FileText className="mr-2 h-3.5 w-3.5" />
                    <span className="truncate">{doc.name}</span>
                    <Download className="ml-auto h-3.5 w-3.5 opacity-50" />
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* 3. 투찰가 분석 결과 */}
          <Card className="border-blue-100 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">분석된 최적 투찰 가격</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 추천 투찰가 */}
              <div className="p-5 bg-blue-600 text-white rounded-xl shadow-inner text-center">
                <p className="text-sm text-blue-200 mb-1">추천 투찰가</p>
                <p className="text-2xl font-bold">{result.bidPrice.toLocaleString()}원</p>
              </div>

              {/* 산출 근거 */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-muted-foreground">기초금액</p>
                  <p className="font-bold text-gray-800">{result.basisAmount.toLocaleString()}원</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-muted-foreground">추정 예정가격</p>
                  <p className="font-bold text-gray-800">{result.estimatedPrice.toLocaleString()}원</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-muted-foreground">낙찰하한율</p>
                  <p className="font-bold text-gray-800">{result.minSuccessRate}%</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-muted-foreground">A값</p>
                  <p className="font-bold text-gray-800">{result.aValue.toLocaleString()}원</p>
                </div>
                <div className="col-span-2 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-muted-foreground">낙찰하한가</p>
                  <p className="font-bold text-gray-800">{result.lowerBound.toLocaleString()}원</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 액션 버튼 */}
          <div className="space-y-2 pt-4">
            {!showBidPriceInput ? (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  disabled={bookmarkSaving}
                  onClick={() => handleSaveBookmark('interested')}
                >
                  <Star className="mr-2 h-4 w-4" />
                  관심공고
                </Button>
                <Button
                  variant="default"
                  className="flex-1 bg-green-600 hover:bg-green-700"
                  disabled={bookmarkSaving}
                  onClick={() => setShowBidPriceInput(true)}
                >
                  <CheckCircle className="mr-2 h-4 w-4" />
                  투찰완료
                </Button>
                <Button variant="secondary" className="sm:w-24" onClick={onClose}>
                  닫기
                </Button>
              </div>
            ) : (
              <div className="space-y-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="투찰가를 입력하세요 (원)"
                    value={bidPriceInput}
                    onChange={(e) => setBidPriceInput(e.target.value)}
                    className="flex-1"
                    type="number"
                    autoFocus
                  />
                  <Button
                    disabled={bookmarkSaving}
                    className="bg-green-600 hover:bg-green-700"
                    onClick={handleBidCompletedWithPrice}
                  >
                    투찰완료 저장
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    disabled={bookmarkSaving}
                    onClick={handleBidCompletedWithoutPrice}
                  >
                    가격 없이 저장
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setShowBidPriceInput(false);
                      setBidPriceInput('');
                    }}
                  >
                    취소
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
