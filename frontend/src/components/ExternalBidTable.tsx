import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { formatDateTime14, formatPrice } from '@/lib/externalBidQuery';
import type { ExternalBidItem } from '@/types/externalBid';

interface ExternalBidTableProps {
  bids: ExternalBidItem[];
  currentPage: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  isLoading?: boolean;
  numOfRows: number;
  onNumOfRowsChange: (rows: number) => void;
}

/** 기관별 배지 색. 기관을 한눈에 구분하기 위한 용도. */
const SOURCE_BADGE_CLASS: Record<string, string> = {
  lh: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  kwater: 'bg-sky-50 text-sky-700 border-sky-200',
  kdhc: 'bg-orange-50 text-orange-700 border-orange-200',
  kra: 'bg-violet-50 text-violet-700 border-violet-200',
  kogas: 'bg-rose-50 text-rose-700 border-rose-200',
  kepco: 'bg-amber-50 text-amber-700 border-amber-200',
};

function sourceBadgeClass(source: string): string {
  return SOURCE_BADGE_CLASS[source] ?? 'bg-gray-50 text-gray-700 border-gray-200';
}

function buildPageList(currentPage: number, totalPages: number): (number | string)[] {
  const maxVisible = 5;
  if (totalPages <= maxVisible) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [1];
  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);

  if (start > 2) pages.push('...');
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < totalPages - 1) pages.push('...');
  pages.push(totalPages);

  return pages;
}

export default function ExternalBidTable({
  bids,
  currentPage,
  totalPages,
  totalCount,
  onPageChange,
  isLoading,
  numOfRows,
  onNumOfRowsChange,
}: ExternalBidTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        <span>조회 중입니다...</span>
      </div>
    );
  }

  if (bids.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p>조회 결과가 없습니다.</p>
        <p className="text-sm mt-2">기관·기간·검색어를 변경해 다시 시도해주세요.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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

      <div className="rounded-md border overflow-x-auto">
        <Table className="break-keep">
          <TableHeader>
            <TableRow className="bg-gray-50">
              <TableHead className="w-[104px]">기관</TableHead>
              <TableHead className="min-w-[300px]">공고명</TableHead>
              <TableHead className="w-[92px]">구분</TableHead>
              <TableHead className="w-[100px]">계약방법</TableHead>
              <TableHead className="w-[120px] text-right">추정가격</TableHead>
              <TableHead className="w-[120px]">공고일</TableHead>
              <TableHead className="w-[136px]">입찰마감</TableHead>
              <TableHead className="w-[136px]">개찰</TableHead>
              <TableHead className="w-[96px]">상태</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bids.map((bid) => (
              <TableRow
                key={`${bid.source}-${bid.noticeNo}-${bid.noticeOrd}`}
                className="hover:bg-blue-50/40"
              >
                <TableCell>
                  <Badge variant="outline" className={sourceBadgeClass(bid.source)}>
                    {bid.sourceName}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="font-medium text-gray-900">{bid.title || '-'}</div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {bid.noticeNo}
                    {bid.institution ? ` · ${bid.institution}` : ''}
                  </div>
                </TableCell>
                <TableCell className="text-sm">{bid.workDiv || '-'}</TableCell>
                <TableCell className="text-sm">{bid.cntrctMthd || '-'}</TableCell>
                <TableCell className="text-right font-semibold whitespace-nowrap">
                  {formatPrice(bid.presmptPrce)}
                </TableCell>
                <TableCell className="text-sm whitespace-nowrap">
                  {formatDateTime14(bid.rgstDt)}
                </TableCell>
                <TableCell className="text-sm whitespace-nowrap">
                  {formatDateTime14(bid.bidCloseDt)}
                </TableCell>
                <TableCell className="text-sm whitespace-nowrap">
                  {formatDateTime14(bid.opengDt)}
                </TableCell>
                <TableCell className="text-sm">{bid.status || '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          {buildPageList(currentPage, totalPages).map((page, idx) =>
            typeof page === 'number' ? (
              <Button
                key={page}
                variant={page === currentPage ? 'default' : 'outline'}
                size="sm"
                className="w-9"
                onClick={() => onPageChange(page)}
              >
                {page}
              </Button>
            ) : (
              <span key={`gap-${idx}`} className="px-1 text-gray-400">
                …
              </span>
            ),
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
