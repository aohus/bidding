import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { BidItem } from '@/types/bid';
import { Calculator } from 'lucide-react';

interface BidTableProps {
  bids: BidItem[];
  onCalculate: (bid: BidItem) => void;
}

export default function BidTable({ bids, onCalculate }: BidTableProps) {
  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr.length < 12) return dateStr;
    const year = dateStr.substring(0, 4);
    const month = dateStr.substring(4, 6);
    const day = dateStr.substring(6, 8);
    const hour = dateStr.substring(8, 10);
    const minute = dateStr.substring(10, 12);
    return `${year}-${month}-${day} ${hour}:${minute}`;
  };

  const formatPrice = (price: string) => {
    const num = parseFloat(price || '0');
    if (num >= 100000000) {
      return `${(num / 100000000).toFixed(1)}억원`;
    } else if (num >= 10000) {
      return `${(num / 10000).toFixed(0)}만원`;
    }
    return `${num.toLocaleString()}원`;
  };

  if (bids.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p>검색 결과가 없습니다.</p>
        <p className="text-sm mt-2">검색 조건을 변경하여 다시 시도해주세요.</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px]">번호</TableHead>
            <TableHead className="min-w-[300px]">입찰공고명</TableHead>
            <TableHead className="min-w-[150px]">공고기관</TableHead>
            <TableHead className="min-w-[120px]">추정가격</TableHead>
            <TableHead className="min-w-[150px]">입찰마감일시</TableHead>
            <TableHead className="min-w-[150px]">개찰일시</TableHead>
            <TableHead className="min-w-[100px]">낙찰방법</TableHead>
            <TableHead className="w-[100px]">투찰</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {bids.map((bid, index) => (
            <TableRow key={`${bid.bidNtceNo}-${bid.bidNtceOrd}`}>
              <TableCell className="font-medium">{index + 1}</TableCell>
              <TableCell>
                <div>
                  <p className="font-medium">{bid.bidNtceNm}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {bid.bidNtceNo}-{bid.bidNtceOrd}
                  </p>
                  {bid.cnstrtsiteRgnNm && (
                    <Badge variant="outline" className="mt-1">
                      {bid.cnstrtsiteRgnNm}
                    </Badge>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <div>
                  <p className="text-sm">{bid.ntceInsttNm}</p>
                  {bid.dminsttNm && bid.dminsttNm !== bid.ntceInsttNm && (
                    <p className="text-xs text-muted-foreground">수요: {bid.dminsttNm}</p>
                  )}
                </div>
              </TableCell>
              <TableCell className="font-semibold">{formatPrice(bid.presmptPrce)}</TableCell>
              <TableCell className="text-sm">{formatDate(bid.bidClseDt)}</TableCell>
              <TableCell className="text-sm">{formatDate(bid.opengDt)}</TableCell>
              <TableCell>
                <Badge variant="secondary" className="text-xs">
                  {bid.sucsfbidMthdNm || '미제공'}
                </Badge>
              </TableCell>
              <TableCell>
                <Button size="sm" onClick={() => onCalculate(bid)} className="w-full">
                  <Calculator className="mr-1 h-4 w-4" />
                  투찰
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}