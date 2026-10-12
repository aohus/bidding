import { useCallback, useEffect, useState } from 'react';
import { format } from 'date-fns';
import { ko } from 'date-fns/locale';
import type { DateRange } from 'react-day-picker';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar as CalendarIcon, Search } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { backendApi } from '@/lib/backendApi';
import ExternalBidTable from '@/components/ExternalBidTable';
import type {
  ExternalBidItem,
  ExternalBidSearchInput,
  ExternalSourceInfo,
} from '@/types/externalBid';

const DEFAULT_ROWS = 100;
const DEFAULT_RANGE_DAYS = 7;

function daysAgo(days: number): Date {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date;
}

function toInputDate(date: Date | undefined): string {
  return date ? format(date, 'yyyy-MM-dd') : '';
}

/**
 * 외부기관 공고 조회 패널.
 *
 * 검색 상태와 조회를 자체적으로 들고 있는 컨테이너다 — 나라장터 검색
 * (Index.tsx / useSearchState)과 상태를 공유하지 않는다. 필터 축이 다르고
 * (지역·업종 대신 기관), 한쪽 탭 조작이 다른 탭 결과를 바꾸면 안 된다.
 */
export default function ExternalBidPanel() {
  const [sources, setSources] = useState<ExternalSourceInfo[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: daysAgo(DEFAULT_RANGE_DAYS),
    to: new Date(),
  });
  const [keyword, setKeyword] = useState('');

  const [bids, setBids] = useState<ExternalBidItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [numOfRows, setNumOfRows] = useState(DEFAULT_ROWS);
  const [isLoading, setIsLoading] = useState(false);

  const totalPages = Math.ceil(totalCount / numOfRows) || 0;

  useEffect(() => {
    backendApi
      .getExternalSources()
      .then(setSources)
      .catch(() => toast.error('기관 목록을 불러오지 못했습니다'));
  }, []);

  const runSearch = useCallback(
    async (page: number, rows: number, input: ExternalBidSearchInput) => {
      setIsLoading(true);
      try {
        const response = await backendApi.searchExternalBids(input, page, rows);
        setBids(response.items);
        setTotalCount(response.totalCount);
        setCurrentPage(page);
        if (response.totalCount === 0) {
          toast.info('조회 결과가 없습니다');
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : '조회 실패');
        setBids([]);
        setTotalCount(0);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const currentInput = useCallback(
    (): ExternalBidSearchInput => ({
      sources: selectedSources,
      dateFrom: toInputDate(dateRange?.from),
      dateTo: toInputDate(dateRange?.to),
      keyword,
    }),
    [selectedSources, dateRange, keyword],
  );

  // 탭 진입 시 1회 자동 조회 — 빈 화면으로 시작하지 않게 한다.
  useEffect(() => {
    runSearch(1, DEFAULT_ROWS, {
      sources: [],
      dateFrom: toInputDate(daysAgo(DEFAULT_RANGE_DAYS)),
      dateTo: toInputDate(new Date()),
      keyword: '',
    });
  }, [runSearch]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    runSearch(1, numOfRows, currentInput());
  };

  const handlePageChange = (page: number) => {
    if (page < 1 || page > totalPages) return;
    runSearch(page, numOfRows, currentInput());
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleRowsChange = (rows: number) => {
    setNumOfRows(rows);
    runSearch(1, rows, currentInput());
  };

  const toggleSource = (source: string, checked: boolean) => {
    setSelectedSources((prev) =>
      checked ? [...prev, source] : prev.filter((s) => s !== source),
    );
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-lg">외부기관 공고 조회</CardTitle>
          <p className="text-sm text-muted-foreground">
            나라장터 외 공공기관 자체 전자입찰 공고입니다. 기관에 따라 추정가격·개찰일시를
            제공하지 않을 수 있고, 참가가능지역·허용업종 정보는 제공되지 않습니다.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>기관 (미선택 시 전체)</Label>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {sources.map((source) => (
                  <label
                    key={source.source}
                    className="flex items-center gap-2 text-sm cursor-pointer"
                  >
                    <Checkbox
                      checked={selectedSources.includes(source.source)}
                      onCheckedChange={(checked) =>
                        toggleSource(source.source, checked === true)
                      }
                    />
                    <span>{source.name}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-[minmax(0,240px)_1fr_auto] md:items-end">
              <div className="space-y-2">
                <Label>공고일 기간</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      className={cn(
                        'w-full justify-start text-left font-normal',
                        !dateRange && 'text-muted-foreground',
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
                      {dateRange?.from ? (
                        dateRange.to ? (
                          <span className="truncate">
                            {format(dateRange.from, 'yy.MM.dd')} ~{' '}
                            {format(dateRange.to, 'yy.MM.dd')}
                          </span>
                        ) : (
                          format(dateRange.from, 'yy.MM.dd')
                        )
                      ) : (
                        <span>기간 선택</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      initialFocus
                      mode="range"
                      defaultMonth={dateRange?.from}
                      selected={dateRange}
                      onSelect={setDateRange}
                      numberOfMonths={1}
                      locale={ko}
                    />
                  </PopoverContent>
                </Popover>
              </div>

              <div className="space-y-2">
                <Label htmlFor="external-keyword">검색어 (공고명·기관명)</Label>
                <Input
                  id="external-keyword"
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  placeholder="예: 공사, 용역, 구매"
                />
              </div>

              <Button type="submit" disabled={isLoading} className="md:w-28">
                <Search className="mr-2 h-4 w-4" />
                조회
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-800">조회 결과</h2>
            {totalCount > 0 && (
              <span className="text-sm text-gray-500">
                전체 <strong>{totalCount.toLocaleString()}</strong>건
              </span>
            )}
          </div>

          <ExternalBidTable
            bids={bids}
            currentPage={currentPage}
            totalPages={totalPages}
            totalCount={totalCount}
            onPageChange={handlePageChange}
            isLoading={isLoading}
            numOfRows={numOfRows}
            onNumOfRowsChange={handleRowsChange}
          />
        </div>
      </div>
    </div>
  );
}
