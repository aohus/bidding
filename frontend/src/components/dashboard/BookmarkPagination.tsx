import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { BookmarkListMeta } from '@/types/bid';

const WINDOW = 2;

interface Props {
  meta: BookmarkListMeta;
  onPageChange: (page: number) => void;
}

export default function BookmarkPagination({ meta, onPageChange }: Props) {
  const { page, total_pages } = meta;
  if (total_pages <= 1) return null;

  const pages: (number | 'ellipsis')[] = [];

  const lo = Math.max(1, page - WINDOW);
  const hi = Math.min(total_pages, page + WINDOW);

  if (lo > 1) {
    pages.push(1);
    if (lo > 2) pages.push('ellipsis');
  }
  for (let i = lo; i <= hi; i++) pages.push(i);
  if (hi < total_pages) {
    if (hi < total_pages - 1) pages.push('ellipsis');
    pages.push(total_pages);
  }

  return (
    <Pagination className="mt-4">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            onClick={page > 1 ? () => onPageChange(page - 1) : undefined}
            className={page <= 1 ? 'pointer-events-none opacity-40' : 'cursor-pointer'}
            href="#"
          />
        </PaginationItem>

        {pages.map((p, idx) =>
          p === 'ellipsis' ? (
            <PaginationItem key={`ellipsis-${idx}`}>
              <PaginationEllipsis />
            </PaginationItem>
          ) : (
            <PaginationItem key={p}>
              <PaginationLink
                href="#"
                isActive={p === page}
                onClick={() => onPageChange(p)}
                className="cursor-pointer"
              >
                {p}
              </PaginationLink>
            </PaginationItem>
          )
        )}

        <PaginationItem>
          <PaginationNext
            onClick={page < total_pages ? () => onPageChange(page + 1) : undefined}
            className={page >= total_pages ? 'pointer-events-none opacity-40' : 'cursor-pointer'}
            href="#"
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}
