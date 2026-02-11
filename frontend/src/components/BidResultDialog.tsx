import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Trophy, Users } from 'lucide-react';
import { backendApi } from '@/lib/backendApi';
import { BidResultResponse } from '@/types/bid';
import { toast } from 'sonner';

interface BidResultDialogProps {
  bidNtceNo: string | null;
  bidNoticeName?: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function BidResultDialog({
  bidNtceNo,
  bidNoticeName,
  isOpen,
  onClose,
}: BidResultDialogProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<BidResultResponse | null>(null);

  useEffect(() => {
    if (isOpen && bidNtceNo) {
      loadResults(bidNtceNo);
    }
  }, [isOpen, bidNtceNo]);

  const loadResults = async (ntceNo: string) => {
    try {
      setLoading(true);
      setData(null);
      const result = await backendApi.getBidResults(ntceNo);
      setData(result);
    } catch (error) {
      toast.error('개찰결과 조회에 실패했습니다');
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price?: string) => {
    if (!price) return '-';
    const num = parseFloat(price);
    return isNaN(num) ? price : num.toLocaleString() + '원';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-yellow-500" />
            개찰결과
          </DialogTitle>
          {bidNoticeName && (
            <p className="text-sm text-gray-600 mt-1">{bidNoticeName}</p>
          )}
        </DialogHeader>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
            <p className="mt-4 text-gray-600">개찰결과를 조회하는 중...</p>
          </div>
        ) : !data || data.results.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            개찰결과가 없습니다
          </div>
        ) : (
          <div className="space-y-4">
            {/* 내 결과 요약 */}
            {data.user_rank && (
              <Card className="border-blue-200 bg-blue-50">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Users className="h-4 w-4 text-blue-600" />
                    <span className="font-semibold text-blue-800">내 투찰 결과</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                    <div>
                      <p className="text-gray-500">순위</p>
                      <p className="font-bold text-lg text-blue-700">
                        {data.user_rank.opengRank || '-'}위
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">투찰률</p>
                      <p className="font-bold text-lg">
                        {data.user_rank.bidprcrt || '-'}%
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">투찰금액</p>
                      <p className="font-bold">{formatPrice(data.user_rank.bidprcAmt)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">총 참여자</p>
                      <p className="font-bold text-lg">{data.total_bidders}명</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 전체 결과 테이블 */}
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[60px]">순위</TableHead>
                    <TableHead>업체명</TableHead>
                    <TableHead className="text-right">투찰금액</TableHead>
                    <TableHead className="w-[80px] text-right">투찰률</TableHead>
                    <TableHead className="w-[80px]">비고</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.results.map((item, idx) => {
                    const isMe =
                      data.user_rank &&
                      item.prcbdrBizno &&
                      data.user_rank.prcbdrBizno &&
                      item.prcbdrBizno.replace(/-/g, '') ===
                        data.user_rank.prcbdrBizno.replace(/-/g, '');

                    return (
                      <TableRow
                        key={idx}
                        className={isMe ? 'bg-blue-50 font-semibold' : ''}
                      >
                        <TableCell className="text-center">
                          {item.opengRank || '-'}
                        </TableCell>
                        <TableCell>
                          {item.prcbdrNm || '-'}
                          {isMe && (
                            <span className="ml-2 text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded">
                              나
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatPrice(item.bidprcAmt)}
                        </TableCell>
                        <TableCell className="text-right">
                          {item.bidprcrt ? `${item.bidprcrt}%` : '-'}
                        </TableCell>
                        <TableCell className="text-xs text-gray-500">
                          {item.rmrk || ''}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
