import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidSearchParams } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Save } from 'lucide-react';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidSearchParams } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Save, Calendar as CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { DateRange } from 'react-day-picker';
import { cn } from '@/lib/utils';
import { Calendar } from '@/components/ui/calendar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

interface SearchFormProps {
  onSearch: (params: BidSearchParams, page?: number) => void;
  isLoading: boolean;
  initialValues?: BidSearchParams | null;
}

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidSearchParams } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Save, Calendar as CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { DateRange } from 'react-day-picker';
import { cn } from '@/lib/utils';
import { Calendar } from '@/components/ui/calendar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { TagInput } from './ui/tag-input';

interface SearchFormProps {
  onSearch: (params: BidSearchParams, page?: number) => void;
  isLoading: boolean;
  initialValues?: BidSearchParams | null;
}

export default function SearchForm({ onSearch, isLoading, initialValues }: SearchFormProps) {
  const [inqryDiv, setInqryDiv] = useState<'1' | '2'>('1');
  const [date, setDate] = useState<DateRange | undefined>({
    from: undefined,
    to: undefined,
  });
  const [regions, setRegions] = useState<string[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [priceStart, setPriceStart] = useState('');
  const [priceEnd, setPriceEnd] = useState('');
  const [excludeClosed, setExcludeClosed] = useState<'Y' | 'N'>('N');

  // Load saved preferences or initial values on mount/update
  useEffect(() => {
    if (initialValues) {
      setInqryDiv(initialValues.inqryDiv);
      
      const parseDate = (dtStr: string) => {
        if (dtStr.length < 8) return undefined;
        const y = parseInt(dtStr.substring(0, 4), 10);
        const m = parseInt(dtStr.substring(4, 6), 10) - 1;
        const d = parseInt(dtStr.substring(6, 8), 10);
        return new Date(y, m, d);
      };

      if (initialValues.inqryBgnDt && initialValues.inqryEndDt) {
        setDate({
          from: parseDate(initialValues.inqryBgnDt),
          to: parseDate(initialValues.inqryEndDt),
        });
      }
      
      setRegions(initialValues.prtcptLmtRgnNm ? initialValues.prtcptLmtRgnNm.split(',').map(s => s.trim()) : []);
      setIndustries(initialValues.indstrytyNm ? initialValues.indstrytyNm.split(',').map(s => s.trim()) : []);
      setPriceStart(initialValues.presmptPrceBgn || '');
      setPriceEnd(initialValues.presmptPrceEnd || '');
      setExcludeClosed(initialValues.bidClseExcpYn || 'N');
    } else {
      loadPreferences();
    }
  }, [initialValues]);

  const loadPreferences = async () => {
    try {
      const preference = await backendApi.getPreference();
      if (preference && preference.search_conditions) {
        const conditions = preference.search_conditions;
        if (conditions.inqryDiv) setInqryDiv(conditions.inqryDiv as '1' | '2');
        
        if (conditions.startDate && conditions.endDate) {
            setDate({
                from: new Date(conditions.startDate as string),
                to: new Date(conditions.endDate as string)
            });
        }

        if (conditions.regions) setRegions(conditions.regions as string[]);
        if (conditions.industries) setIndustries(conditions.industries as string[]);
        if (conditions.priceStart) setPriceStart(conditions.priceStart as string);
        if (conditions.priceEnd) setPriceEnd(conditions.priceEnd as string);
        if (conditions.excludeClosed) setExcludeClosed(conditions.excludeClosed as 'Y' | 'N' );
        toast.success('저장된 검색 조건을 불러왔습니다');
      }
    } catch (error) {
      // Silently fail if no preferences exist
      console.log('No saved preferences found');
    }
  };

  const savePreferences = async () => {
    try {
      await backendApi.savePreference({
        inqryDiv,
        startDate: date?.from?.toISOString(),
        endDate: date?.to?.toISOString(),
        regions,
        industries,
        priceStart,
        priceEnd,
        excludeClosed,
      });
      toast.success('검색 조건이 저장되었습니다');
    } catch (error) {
      toast.error('검색 조건 저장 실패');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!date?.from || !date?.to) {
      toast.error('조회 기간을 선택해주세요');
      return;
    }

    const formatDateTime = (d: Date, end: boolean = false) => {
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${year}${month}${day}${end ? '2359' : '0000'}`;
    };

    const params: BidSearchParams = {
      inqryDiv,
      inqryBgnDt: formatDateTime(date.from),
      inqryEndDt: formatDateTime(date.to, true),
      prtcptLmtRgnNm: regions.length > 0 ? regions.join(',') : undefined,
      indstrytyNm: industries.length > 0 ? industries.join(',') : undefined,
      presmptPrceBgn: priceStart || undefined,
      presmptPrceEnd: priceEnd || undefined,
      bidClseExcpYn: excludeClosed || undefined,
    };

    // Always start from page 1 when submitting a new search
    onSearch(params, 1);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>입찰 공고 검색</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 기본 필터 */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label htmlFor="inqryDiv">조회 구분</Label>
              <Select value={inqryDiv} onValueChange={(value: '1' | '2') => setInqryDiv(value)}>
                <SelectTrigger id="inqryDiv">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">공고게시일시</SelectItem>
                  <SelectItem value="2">개찰일시</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2 md:col-span-2">
              <Label>조회 기간</Label>
              <div className={cn("grid gap-2")}>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      id="date"
                      variant={"outline"}
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !date && "text-muted-foreground"
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {date?.from ? (
                        date.to ? (
                          <>
                            {format(date.from, "yyyy-MM-dd")} -{" "}
                            {format(date.to, "yyyy-MM-dd")}
                          </>
                        ) : (
                          format(date.from, "yyyy-MM-dd")
                        )
                      ) : (
                        <span>기간을 선택하세요</span>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      initialFocus
                      mode="range"
                      defaultMonth={date?.from}
                      selected={date}
                      onSelect={setDate}
                      numberOfMonths={2}
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="bidClseExcpYn">입찰마감 제외 여부</Label>
              <Select
                value={excludeClosed}
                onValueChange={(value: 'Y' | 'N' ) => setExcludeClosed(value)}
              >
                <SelectTrigger id="bidClseExcpYn">
                  <SelectValue placeholder="제외" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Y">제외</SelectItem>
                  <SelectItem value="N">포함</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>참가제한지역명 (선택)</Label>
              <TagInput
                placeholder="예: 서울특별시"
                tags={regions}
                onChange={setRegions}
              />
            </div>

            <div className="space-y-2">
              <Label>업종명 (선택)</Label>
              <TagInput
                placeholder="예: 토목건축"
                tags={industries}
                onChange={setIndustries}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="priceStart">추정가격 시작 (선택)</Label>
              <Input
                id="priceStart"
                type="text"
                inputMode="numeric"
                placeholder="예: 100000000"
                value={priceStart}
                onChange={(e) => setPriceStart(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="priceEnd">추정가격 종료 (선택)</Label>
              <Input
                id="priceEnd"
                type="text"
                inputMode="numeric"
                placeholder="예: 500000000"
                value={priceEnd}
                onChange={(e) => setPriceEnd(e.target.value)}
              />
            </div>
          </div>


          <div className="flex gap-2">
            <Button type="submit" className="flex-1" disabled={isLoading}>
              {isLoading ? '검색 중...' : '검색'}
            </Button>
            <Button type="button" variant="outline" onClick={savePreferences}>
              <Save className="mr-2 h-4 w-4" />
              조건 저장
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
