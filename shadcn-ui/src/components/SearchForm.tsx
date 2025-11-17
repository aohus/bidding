import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface SearchFormProps {
  onSearch: (params: {
    inqryDiv: '1' | '2';
    inqryBgnDt: string;
    inqryEndDt: string;
    prtcptLmtRgnCd?: string;
    presmptPrceBgn?: string;
    presmptPrceEnd?: string;
  }) => void;
  isLoading: boolean;
}

const REGIONS = [
  { code: '00', name: '전국' },
  { code: '11', name: '서울특별시' },
  { code: '26', name: '부산광역시' },
  { code: '27', name: '대구광역시' },
  { code: '28', name: '인천광역시' },
  { code: '29', name: '광주광역시' },
  { code: '30', name: '대전광역시' },
  { code: '31', name: '울산광역시' },
  { code: '36', name: '세종특별자치시' },
  { code: '41', name: '경기도' },
  { code: '42', name: '강원도' },
  { code: '43', name: '충청북도' },
  { code: '44', name: '충청남도' },
  { code: '45', name: '전라북도' },
  { code: '46', name: '전라남도' },
  { code: '47', name: '경상북도' },
  { code: '48', name: '경상남도' },
  { code: '50', name: '제주도' },
];

export default function SearchForm({ onSearch, isLoading }: SearchFormProps) {
  const [inqryDiv, setInqryDiv] = useState<'1' | '2'>('1');
  const [startDate, setStartDate] = useState<Date>();
  const [endDate, setEndDate] = useState<Date>();
  const [region, setRegion] = useState<string>('');
  const [minBudget, setMinBudget] = useState<string>('');
  const [maxBudget, setMaxBudget] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!startDate || !endDate) {
      alert('날짜 범위를 선택해주세요.');
      return;
    }

    const formatDate = (date: Date) => {
      return format(date, 'yyyyMMddHHmm');
    };

    onSearch({
      inqryDiv,
      inqryBgnDt: formatDate(startDate),
      inqryEndDt: formatDate(endDate),
      prtcptLmtRgnCd: region || undefined,
      presmptPrceBgn: minBudget || undefined,
      presmptPrceEnd: maxBudget || undefined,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>입찰공고 검색</CardTitle>
        <CardDescription>검색 조건을 입력하여 입찰공고를 조회하세요</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="inqryDiv">조회 구분</Label>
              <Select value={inqryDiv} onValueChange={(value) => setInqryDiv(value as '1' | '2')}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">공고게시일시</SelectItem>
                  <SelectItem value="2">개찰일시</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>지역</Label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger>
                  <SelectValue placeholder="지역 선택 (선택사항)" />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r.code} value={r.code}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>시작일</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn('w-full justify-start text-left font-normal', !startDate && 'text-muted-foreground')}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {startDate ? format(startDate, 'yyyy-MM-dd') : '날짜 선택'}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar mode="single" selected={startDate} onSelect={setStartDate} initialFocus />
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label>종료일</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn('w-full justify-start text-left font-normal', !endDate && 'text-muted-foreground')}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {endDate ? format(endDate, 'yyyy-MM-dd') : '날짜 선택'}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar mode="single" selected={endDate} onSelect={setEndDate} initialFocus />
                </PopoverContent>
              </Popover>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="minBudget">최소 추정가격 (원)</Label>
              <Input
                id="minBudget"
                type="number"
                placeholder="예: 10000000"
                value={minBudget}
                onChange={(e) => setMinBudget(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxBudget">최대 추정가격 (원)</Label>
              <Input
                id="maxBudget"
                type="number"
                placeholder="예: 100000000"
                value={maxBudget}
                onChange={(e) => setMaxBudget(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? '검색 중...' : '검색'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}