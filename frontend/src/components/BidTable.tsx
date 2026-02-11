import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { BidItem } from '@/types/bid';
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ChevronsUpDown, Loader2, Heart, CheckCircle2 } from 'lucide-react';

export interface BookmarkInfo {
  status: string;
  bookmarkId: string;
}

interface BidTableProps {
  bids: BidItem[];
  onBidClick: (bid: BidItem) => void;
  currentPage: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  isLoading?: boolean;
  numOfRows: number;
  onNumOfRowsChange: (rows: number) => void;
  orderBy?: string;
  orderDir?: 'asc' | 'desc';
  onSort: (field: string) => void;
  bookmarkMap?: Map<string, BookmarkInfo>;
  onBookmarkToggle?: (bid: BidItem, status: 'interested' | 'bid_completed') => void;
}

export default function BidTable({
  bids,
  onBidClick,
  currentPage,
  totalPages,
  totalCount,
  onPageChange,
  isLoading,
  numOfRows,
  onNumOfRowsChange,
  orderBy,
  orderDir,
  onSort,
  bookmarkMap,
  onBookmarkToggle,
}: BidTableProps) {
  const formatPrice = (price: string) => {
    const num = parseFloat(price || '0');
    if (num >= 100000000) {
      return `${(num / 100000000).toFixed(1)}억원`;
    } else if (num >= 10000) {
      return `${(num / 10000).toFixed(0)}만원`;
    }
    return `${num.toLocaleString()}원`;
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (orderBy !== field) return <ChevronsUpDown className="h-3 w-3 ml-1 opacity-30" />;
    return orderDir === 'asc'
      ? <ChevronUp className="h-3 w-3 ml-1" />
      : <ChevronDown className="h-3 w-3 ml-1" />;
  };

  const SortableHead = ({ field, children, className = '' }: { field: string; children: React.ReactNode; className?: string }) => (
    <TableHead
      className={`whitespace-nowrap cursor-pointer select-none hover:bg-muted/50 ${className}`}
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center">
        {children}
        <SortIcon field={field} />
      </span>
    </TableHead>
  );

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisiblePages = 5;

    if (totalPages <= maxVisiblePages) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);

      let startPage = Math.max(2, currentPage - 1);
      let endPage = Math.min(totalPages - 1, currentPage + 1);

      if (currentPage <= 3) {
        endPage = Math.min(totalPages - 1, 4);
      }

      if (currentPage >= totalPages - 2) {
        startPage = Math.max(2, totalPages - 3);
      }

      if (startPage > 2) {
        pages.push('...');
      }

      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }

      if (endPage < totalPages - 1) {
        pages.push('...');
      }

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
        <div className="flex items-center gap-3">
          <span>
            총 <span className="font-semibold text-gray-900">{totalCount.toLocaleString()}</span>개
          </span>
          <Select value={String(numOfRows)} onValueChange={(v) => onNumOfRowsChange(Number(v))}>
            <SelectTrigger className="h-7 w-[80px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="20">20줄</SelectItem>
              <SelectItem value="50">50줄</SelectItem>
              <SelectItem value="100">100줄</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <span>
          <span className="font-semibold text-gray-900">{currentPage}</span> / {totalPages} 페이지
        </span>
      </div>

      {/* Table */}
      <div className="rounded-md border overflow-x-auto">
        <Table className="break-keep table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[36px] whitespace-nowrap">#</TableHead>
              <TableHead className="w-[56px] whitespace-nowrap text-center">저장</TableHead>
              <TableHead className="w-[200px] whitespace-nowrap">공고명</TableHead>
              <TableHead className="w-[120px] whitespace-nowrap">현장</TableHead>
              <SortableHead field="bdgtAmt" className="w-[80px]">예산</SortableHead>
              <SortableHead field="presmptPrce" className="w-[80px]">추정가</SortableHead>
              <SortableHead field="bidClseDt" className="w-[88px]">마감일시</SortableHead>
              <TableHead className="w-[90px] whitespace-nowrap">계약방법</TableHead>
              <TableHead className="w-[130px] whitespace-nowrap">허용업종</TableHead>
              <TableHead className="w-[110px]">참가지역</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bids.map((bid, index) => {
              const globalIndex = (currentPage - 1) * numOfRows + index + 1;
              return (
                <TableRow key={`${bid.bidNtceNo}-${bid.bidNtceOrd}`}>
                  <TableCell className="font-medium">{globalIndex}</TableCell>
                  <TableCell className="text-center">
                    {(() => {
                      const bm = bookmarkMap?.get(bid.bidNtceNo);
                      const isInterested = bm?.status === 'interested';
                      const isBidCompleted = bm?.status === 'bid_completed';
                      return (
                        <div className="flex items-center justify-center gap-1">
                          <button
                            type="button"
                            title="관심공고"
                            className="p-0.5 rounded hover:bg-red-50 transition-colors"
                            onClick={(e) => {
                              e.stopPropagation();
                              onBookmarkToggle?.(bid, 'interested');
                            }}
                          >
                            <Heart
                              className={`h-4 w-4 ${isInterested ? 'fill-red-500 text-red-500' : 'text-gray-300 hover:text-red-400'}`}
                            />
                          </button>
                          <button
                            type="button"
                            title="투찰완료"
                            className="p-0.5 rounded hover:bg-green-50 transition-colors"
                            onClick={(e) => {
                              e.stopPropagation();
                              onBookmarkToggle?.(bid, 'bid_completed');
                            }}
                          >
                            <CheckCircle2
                              className={`h-4 w-4 ${isBidCompleted ? 'fill-green-500 text-green-500' : 'text-gray-300 hover:text-green-400'}`}
                            />
                          </button>
                        </div>
                      );
                    })()}
                  </TableCell>
                  <TableCell className="max-w-[200px]">
                    <button
                      type="button"
                      className="text-left w-full group"
                      onClick={() => onBidClick(bid)}
                      disabled={isLoading}
                    >
                      <p className="font-medium text-blue-600 group-hover:text-blue-800 group-hover:underline cursor-pointer line-clamp-2" title={bid.bidNtceNm}>
                        {isLoading ? (
                          <span className="inline-flex items-center gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            {bid.bidNtceNm}
                          </span>
                        ) : bid.bidNtceNm}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {bid.bidNtceNo}-{bid.bidNtceOrd}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                          {bid.ntceInsttNm}
                        </Badge>
                        {bid.dminsttNm && bid.dminsttNm !== bid.ntceInsttNm && (
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                            수요: {bid.dminsttNm}
                          </Badge>
                        )}
                      </div>
                    </button>
                  </TableCell>
                  <TableCell className="text-sm">
                    {bid.cnstrtsiteRgnNm || <span className="text-muted-foreground">-</span>}
                  </TableCell>
                  <TableCell className="font-semibold whitespace-nowrap">{formatPrice(bid.bdgtAmt)}</TableCell>
                  <TableCell className="font-semibold whitespace-nowrap">{formatPrice(bid.presmptPrce)}</TableCell>
                  <TableCell className="text-sm whitespace-nowrap">
                    {bid.bidClseDt ? (
                      <>
                        <span>{bid.bidClseDt.split(' ')[0]}</span>
                        <br />
                        <span className="text-muted-foreground">{bid.bidClseDt.split(' ')[1]}</span>
                      </>
                    ) : '-'}
                  </TableCell>
                  <TableCell className="text-sm whitespace-nowrap">{bid.cntrctCnclsMthdNm || ''}</TableCell>
                  <TableCell className="text-sm whitespace-nowrap">
                    {bid.permsnIndstrytyListNms ? (
                      <span title={bid.permsnIndstrytyListNms}>
                        {bid.permsnIndstrytyListNms.length > 12
                          ? `${bid.permsnIndstrytyListNms.substring(0, 12)}…`
                          : bid.permsnIndstrytyListNms}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                    {bid.indstrytyMfrcFldListNms && (
                      <p className="text-xs text-orange-600 mt-0.5" title={bid.indstrytyMfrcFldListNms}>
                        {bid.indstrytyMfrcFldListNms.length > 12
                          ? `${bid.indstrytyMfrcFldListNms.substring(0, 12)}…`
                          : bid.indstrytyMfrcFldListNms}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {bid.prtcptPsblRgnNms ? (
                      <span>{bid.prtcptPsblRgnNms}</span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
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
