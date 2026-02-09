import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidAValueItem, BidItem } from '@/types/bid';
import { calculateOptimalBidPrice } from '@/lib/bidCalculations';
import { downloadDocument } from '@/lib/api';
import { Download, FileText, Calculator, Gavel } from 'lucide-react';


interface BidCalculatorProps {
  bid: BidItem | null;
  aValueItem: BidAValueItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function BidCalculator({ bid, aValueItem, isOpen, onClose }: BidCalculatorProps) {
  if (!bid) return null;

  // 기초금액(Basis Amount) 결정: 상세 API에서 받은 bssamt가 최우선, 없으면 검색 결과의 bdgtAmt 사용
  const basisAmount = aValueItem?.bssamt ? parseFloat(aValueItem.bssamt) : parseFloat(bid.bdgtAmt || '0');
  const minSuccessRate = parseFloat(bid.sucsfbidLwltRate || '87.745');

  const result = calculateOptimalBidPrice(
    basisAmount, 
    bid.prearngPrceDcsnMthdNm || '미제공', 
    aValueItem, 
    minSuccessRate
  );

  const documents = [
    { url: bid.ntceSpecDocUrl1, name: bid.ntceSpecFileNm1 || '공고규격서 1' },
    { url: bid.ntceSpecDocUrl2, name: bid.ntceSpecFileNm2 || '공고규격서 2' },
    { url: bid.ntceSpecDocUrl3, name: bid.ntceSpecFileNm3 || '공고규격서 3' },
    { url: bid.ntceSpecDocUrl4, name: bid.ntceSpecFileNm4 || '공고규격서 4' },
    { url: bid.ntceSpecDocUrl5, name: bid.ntceSpecFileNm5 || '공고규격서 5' },
    { url: bid.sptDscrptDocUrl1, name: bid.sptDscrptFileNm1 || '현장설명서 1' },
    { url: bid.sptDscrptDocUrl2, name: bid.sptDscrptFileNm2 || '현장설명서 2' },
    { url: bid.sptDscrptDocUrl3, name: bid.sptDscrptFileNm3 || '현장설명서 3' },
    { url: bid.bidNtceDtlUrl, name: '입찰공고 페이지' },
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
          {/* 1. 기본 정보 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">공고번호</span>
                    <span className="font-medium">{bid.bidNtceNo}-{bid.bidNtceOrd}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">기초금액(bssamt)</span>
                    <span className="font-medium text-blue-600">{basisAmount.toLocaleString()}원</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">낙찰하한율</span>
                    <span className="font-medium">{minSuccessRate}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6 space-y-4 text-sm">
                <div className="flex flex-col gap-1.5">
                  <span className="text-muted-foreground flex items-center gap-1">
                    <Gavel className="h-3.5 w-3.5" /> 낙찰방법
                  </span>
                  <div 
                    className="p-2 bg-gray-50 rounded border border-gray-100 text-xs font-medium text-gray-700 leading-relaxed"
                    title={bid.sucsfbidMthdNm}
                  >
                    {bid.sucsfbidMthdNm || '정보 없음'}
                  </div>
                </div>
                <div className="flex justify-between items-center pt-1">
                  <span className="text-muted-foreground">예정가격 결정방식</span>
                  <span className="font-medium">{bid.prearngPrceDcsnMthdNm || '미제공'}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 2. 투찰가 분석 결과 */}
          <Card className="border-blue-100 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">분석된 최적 투찰 가격</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 bg-blue-600 text-white rounded-xl shadow-inner">
                  <p className="text-xs opacity-80 mb-1">최적 투찰가 (통계적 추천)</p>
                  <p className="text-2xl font-bold">{result.optimalPrice.toLocaleString()}원</p>
                </div>
                <div className="p-4 bg-emerald-500 text-white rounded-xl shadow-inner">
                  <p className="text-xs opacity-80 mb-1">권장 투찰가 (안전 마진)</p>
                  <p className="text-2xl font-bold">{result.recommendedPrice.toLocaleString()}원</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-gray-100 rounded-lg">
                  <p className="text-xs text-muted-foreground">하한선 (사정율 100%)</p>
                  <p className="text-md font-bold text-gray-700">{result.minPrice.toLocaleString()}원</p>
                </div>
                <div className="p-3 bg-gray-100 rounded-lg">
                  <p className="text-xs text-muted-foreground">기초금액 (100%)</p>
                  <p className="text-md font-bold text-gray-700">{basisAmount.toLocaleString()}원</p>
                </div>
              </div>

              <div className="p-4 border rounded-lg bg-white">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">계산 산식 및 전략</p>
                <pre className="text-xs text-gray-600 leading-relaxed font-sans whitespace-pre-wrap">
                  {result.calculation}
                </pre>
              </div>
            </CardContent>
          </Card>

          {/* 3. A값 세부 내역 */}
          {result.aValueDetail && (
            <Card className="border-orange-100 bg-orange-50/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-md flex items-center gap-2">
                  기초금액 A값 세부 항목
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs text-orange-800 leading-relaxed font-mono whitespace-pre-wrap">
                  {result.aValueDetail}
                </pre>
              </CardContent>
            </Card>
          )}

          {/* 4. 입찰 서류 목록 */}
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

          <div className="flex justify-end pt-4">
            <Button className="w-full sm:w-32 h-11" onClick={onClose}>
              확인 후 닫기
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}