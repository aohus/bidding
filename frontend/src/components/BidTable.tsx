import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { BidItem } from '@/types/bid';
import { Calculator, ChevronLeft, ChevronRight } from 'lucide-react';

interface BidTableProps {
  bids: BidItem[];
  onCalculate: (bid: BidItem) => void;
  currentPage: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
}

export default function BidTable({ 
  bids, 
  onCalculate, 
  currentPage, 
  totalPages, 
  totalCount,
  onPageChange 
}: BidTableProps) {
  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr.length < 12) return dateStr;
    const year = dateStr.substring(0, 4);
    const month = dateStr.substring(4, 6);
    const day = dateStr.substring(6, 8);
    const hour = dateStr.substring(8, 10);
    const minute = dateStr.substring(10, 12);
    return `${year}-${month}-${day} ${hour}:${minute}}`;
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

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisiblePages = 5;
    
    if (totalPages <= maxVisiblePages) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);
      
      // Calculate range around current page
      let startPage = Math.max(2, currentPage - 1);
      let endPage = Math.min(totalPages - 1, currentPage + 1);
      
      // Adjust if we're near the start
      if (currentPage <= 3) {
        endPage = Math.min(totalPages - 1, 4);
      }
      
      // Adjust if we're near the end
      if (currentPage >= totalPages - 2) {
        startPage = Math.max(2, totalPages - 3);
      }
      
      // Add ellipsis after first page if needed
      if (startPage > 2) {
        pages.push('...');
      }
      
      // Add middle pages
      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }
      
      // Add ellipsis before last page if needed
      if (endPage < totalPages - 1) {
        pages.push('...');
      }
      
      // Always show last page
      pages.push(totalPages);
    }
    
    return pages;
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
    <div className="space-y-4">
      {/* Results summary */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          총 <span className="font-semibold text-gray-900">{totalCount.toLocaleString()}</span>개의 입찰 공고
        </span>
        <span>
          <span className="font-semibold text-gray-900">{currentPage}</span> / {totalPages} 페이지
        </span>
      </div>

      {/* Table */}
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[50px]">번호</TableHead>
              <TableHead className="min-w-[250px]">입찰공고명</TableHead>
              <TableHead className="min-w-[100px]">공고기관</TableHead>
              <TableHead className="min-w-[100px]">예산금액</TableHead>
              <TableHead className="min-w-[100px]">추정가격</TableHead>
              <TableHead className="min-w-[130px]">입찰마감일시</TableHead>
              <TableHead className="min-w-[80px]">예가결정방법</TableHead>
              <TableHead className="min-w-[80px]">계약체결방법</TableHead>
              <TableHead className="min-w-[80px]">주공종명</TableHead>
              <TableHead className="min-w-[80px]">업종제한</TableHead>
              <TableHead className="w-[100px]">투찰</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bids.map((bid, index) => {
              const globalIndex = (currentPage - 1) * 100 + index + 1;
              return (
                <TableRow key={`${bid.bidNtceNo}-${bid.bidNtceOrd}`}>
                  <TableCell className="font-medium">{globalIndex}</TableCell>
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
                  <TableCell className="font-semibold">{formatPrice(bid.bdgtAmt)}</TableCell>
                  <TableCell className="font-semibold">{formatPrice(bid.presmptPrce)}</TableCell>
                  <TableCell className="text-sm">{bid.bidClseDt}</TableCell>
                  <TableCell className="text-sm">{bid.prearngPrceDcsnMthdNm || ""}</TableCell>
                  <TableCell className="text-sm">{bid.cntrctCnclsMthdNm || ''}</TableCell>
                  <TableCell className="text-sm">{bid.mainCnsttyNm || ''}</TableCell>
                  <TableCell className="text-sm">{bid.indstrytyLmtYn === 'Y' ? '있음' : '없음'}</TableCell>
                  <TableCell>
                    <Button size="sm" onClick={() => onCalculate(bid)} className="w-full">
                      <Calculator className="mr-1 h-4 w-4" />
                      투찰
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            이전
          </Button>

          <div className="flex items-center gap-1">
            {getPageNumbers().map((page, index) => {
              if (page === '...') {
                return (
                  <span key={`ellipsis-${index}`} className="px-2 text-gray-400">
                    ...
                  </span>
                );
              }
              
              const pageNum = page as number;
              return (
                <Button
                  key={pageNum}
                  variant={currentPage === pageNum ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => onPageChange(pageNum)}
                  className="min-w-[40px]"
                >
                  {pageNum}
                </Button>
              );
            })}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            다음
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}