import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidSearchParams } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Save, Calendar as CalendarIcon, FolderOpen, Plus } from 'lucide-react';
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
import { SavedSearchList } from './SavedSearchList';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

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

  const [isSavedSearchOpen, setIsSavedSearchOpen] = useState(false);
  const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState('');

  // Load saved preferences or initial values on mount/update
  useEffect(() => {
    if (initialValues) {
      applyFilters(initialValues);
    } else {
      loadPreferences();
    }
  }, [initialValues]);

  const applyFilters = (filters: any) => {
      if (filters.inqryDiv === '1' || filters.inqryDiv === '2') {
          setInqryDiv(filters.inqryDiv);
      } else {
          setInqryDiv('1');
      }
      
      // Handle Date formats: YYYYMMDDHHMM or ISO string
      let fromDate, toDate;
      
      if (filters.startDate) {
          fromDate = new Date(filters.startDate);
      } else if (filters.inqryBgnDt && filters.inqryBgnDt.length >= 8) {
          const y = parseInt(filters.inqryBgnDt.substring(0, 4));
          const m = parseInt(filters.inqryBgnDt.substring(4, 6)) - 1;
          const d = parseInt(filters.inqryBgnDt.substring(6, 8));
          fromDate = new Date(y, m, d);
      }

      if (filters.endDate) {
          toDate = new Date(filters.endDate);
      } else if (filters.inqryEndDt && filters.inqryEndDt.length >= 8) {
          const y = parseInt(filters.inqryEndDt.substring(0, 4));
          const m = parseInt(filters.inqryEndDt.substring(4, 6)) - 1;
          const d = parseInt(filters.inqryEndDt.substring(6, 8));
          toDate = new Date(y, m, d);
      }

      if (fromDate && toDate) {
          setDate({ from: fromDate, to: toDate });
      }

      // Handle arrays or strings
      if (filters.regions) {
          setRegions(filters.regions);
      } else if (filters.prtcptLmtRgnNm) {
          setRegions(filters.prtcptLmtRgnNm.split(',').map((s: string) => s.trim()));
      } else {
          setRegions([]);
      }

      if (filters.industries) {
          setIndustries(filters.industries);
      } else if (filters.indstrytyNm) {
          setIndustries(filters.indstrytyNm.split(',').map((s: string) => s.trim()));
      } else {
          setIndustries([]);
      }

      setPriceStart(filters.priceStart || filters.presmptPrceBgn || '');
      setPriceEnd(filters.priceEnd || filters.presmptPrceEnd || '');
      setExcludeClosed(filters.excludeClosed || filters.bidClseExcpYn || 'N');
  };

  const loadPreferences = async () => {
    try {
      const preference = await backendApi.getPreference();
      if (preference && preference.search_conditions) {
        applyFilters(preference.search_conditions);
        toast.success('기본 검색 조건을 불러왔습니다');
      }
    } catch (error) {
      // Silently fail if no preferences exist
      console.log('No saved preferences found');
    }
  };

  const saveAsDefault = async () => {
    try {
      await backendApi.savePreference(getCurrentFilters());
      toast.success('기본 검색 조건으로 저장되었습니다');
    } catch (error) {
      toast.error('저장 실패');
    }
  };

  const saveAsNew = async () => {
    if (!saveName.trim()) {
        toast.error('검색 조건 이름을 입력해주세요');
        return;
    }
    try {
        await backendApi.createSavedSearch(saveName, getCurrentFilters());
        toast.success('새 검색 조건이 저장되었습니다');
        setIsSaveDialogOpen(false);
        setSaveName('');
    } catch (error) {
        toast.error('저장 실패');
    }
  };

  const getCurrentFilters = () => ({
    inqryDiv,
    startDate: date?.from?.toISOString(),
    endDate: date?.to?.toISOString(),
    regions,
    industries,
    priceStart,
    priceEnd,
    excludeClosed,
  });

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
        <div className="flex justify-between items-center">
            <CardTitle>입찰 공고 검색</CardTitle>
            <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setIsSavedSearchOpen(true)}>
                    <FolderOpen className="mr-2 h-4 w-4" />
                    불러오기
                </Button>
            </div>
        </div>
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
            <Button type="button" variant="outline" onClick={saveAsDefault}>
              <Save className="mr-2 h-4 w-4" />
              기본값 저장
            </Button>
            <Button type="button" variant="outline" onClick={() => setIsSaveDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              새로 저장
            </Button>
          </div>
        </form>

        <SavedSearchList 
            isOpen={isSavedSearchOpen}
            onClose={() => setIsSavedSearchOpen(false)}
            onSelect={(filters) => {
                applyFilters(filters);
                toast.success('검색 조건을 불러왔습니다');
            }}
        />

        <Dialog open={isSaveDialogOpen} onOpenChange={setIsSaveDialogOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>새 검색 조건 저장</DialogTitle>
                </DialogHeader>
                <div className="py-4">
                    <Label htmlFor="saveName">조건 이름</Label>
                    <Input 
                        id="saveName" 
                        value={saveName} 
                        onChange={(e) => setSaveName(e.target.value)} 
                        placeholder="예: 서울 조경 공사"
                    />
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => setIsSaveDialogOpen(false)}>취소</Button>
                    <Button onClick={saveAsNew}>저장</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}