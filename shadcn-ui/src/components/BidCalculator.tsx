import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BidItem } from '@/types/bid';
import { calculateOptimalBidPrice } from '@/lib/bidCalculations';
import { downloadDocument } from '@/lib/api';
import { Download, FileText } from 'lucide-react';

interface BidCalculatorProps {
  bid: BidItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function BidCalculator({ bid, isOpen, onClose }: BidCalculatorProps) {
  if (!bid) return null;

  const estimatedPrice = parseFloat(bid.presmptPrce || '0');
  const minSuccessRate = parseFloat(bid.sucsfbidLwltRate || '87.745');

  const result = calculateOptimalBidPrice(estimatedPrice, bid.prearngPrceDcsnMthdNm || '미제공', minSuccessRate);

  const documents = [
    { url: bid.ntceSpecDocUrl1, name: bid.ntceSpecFileNm1 || '공고규격서 1' },
    { url: bid.ntceSpecDocUrl2, name: bid.ntceSpecFileNm2 || '공고규격서 2' },
    { url: bid.ntceSpecDocUrl3, name: bid.ntceSpecFileNm3 || '공고규격서 3' },
    { url: bid.ntceSpecDocUrl4, name: bid.ntceSpecFileNm4 || '공고규격서 4' },
    { url: bid.ntceSpecDocUrl5, name: bid.ntceSpecFileNm5 || '공고규격서 5' },
    { url: bid.sptDscrptDocUrl1, name: bid.sptDscrptFileNm1 || '현장설명서 1' },
    { url: bid.sptDscrptDocUrl2, name: bid.sptDscrptFileNm2 || '현장설명서 2' },
    { url: bid.sptDscrptDocUrl3, name: bid.sptDscrptFileNm3 || '현장설명서 3' },
    { url: bid.stdNtceDocUrl, name: bid.stdNtceDocFileNm || '표준공고서' },
    { url: bid.bidNtceUrl, name: '입찰공고 페이지' },
    { url: bid.bidNtceDtlUrl, name: '입찰공고 상세' },
  ].filter((doc) => doc.url);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>투찰 가격 계산</DialogTitle>
          <DialogDescription>{bid.bidNtceNm}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">최적 투찰 가격</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <p className="text-sm text-muted-foreground">최적 가격 (권장)</p>
                  <p className="text-2xl font-bold text-blue-600">{result.optimalPrice.toLocaleString()}원</p>
                </div>
                <div className="p-4 bg-green-50 rounded-lg">
                  <p className="text-sm text-muted-foreground">권장 가격</p>
                  <p className="text-2xl font-bold text-green-600">{result.recommendedPrice.toLocaleString()}원</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-muted-foreground">최저 가격</p>
                  <p className="text-lg font-semibold">{result.minPrice.toLocaleString()}원</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-muted-foreground">최고 가격</p>
                  <p className="text-lg font-semibold">{result.maxPrice.toLocaleString()}원</p>
                </div>
              </div>

              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium mb-2">계산 상세</p>
                <pre className="text-xs whitespace-pre-wrap">{result.calculation}</pre>
              </div>
            </CardContent>
          </Card>

          {documents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">입찰 서류</CardTitle>
                <CardDescription>다운로드 가능한 문서 목록</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {documents.map((doc, index) => (
                    <Button
                      key={index}
                      variant="outline"
                      className="w-full justify-start"
                      onClick={() => downloadDocument(doc.url!, doc.name)}
                    >
                      <FileText className="mr-2 h-4 w-4" />
                      {doc.name}
                      <Download className="ml-auto h-4 w-4" />
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={onClose}>
              닫기
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}