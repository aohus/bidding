import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { BidSearchParams, UserLocation } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Save, Calendar as CalendarIcon, FolderOpen, Plus, MapPin, Pencil, Trash2 } from 'lucide-react';
import { format } from 'date-fns';
import { ko } from "date-fns/locale";
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
  const [cnstrtsiteRgnNm, setCnstrtsiteRgnNm] = useState('');
  const [industries, setIndustries] = useState<string[]>([]);
  const [priceStart, setPriceStart] = useState('');
  const [priceEnd, setPriceEnd] = useState('');
  const [excludeClosed, setExcludeClosed] = useState<'Y' | 'N'>('N');

  const [isSavedSearchOpen, setIsSavedSearchOpen] = useState(false);
  const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState('');

  // 소재지 관련 상태
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null);
  const [useLocationFilter, setUseLocationFilter] = useState(false);
  const [isLocationDialogOpen, setIsLocationDialogOpen] = useState(false);
  const [locationInput, setLocationInput] = useState('');

  // 소재지 정보 로드
  useEffect(() => {
    loadLocation();
  }, []);

  const loadLocation = async () => {
    try {
      const location = await backendApi.getLocation();
      setUserLocation(location);
    } catch {
      // 소재지 미등록
    }
  };

  const handleSaveLocation = async () => {
    if (!locationInput.trim()) {
      toast.error('소재지를 입력해주세요');
      return;
    }
    try {
      const location = await backendApi.setLocation(locationInput.trim());
      setUserLocation(location);
      setIsLocationDialogOpen(false);
      setLocationInput('');
      toast.success('소재지가 등록되었습니다');
    } catch {
      toast.error('소재지 등록 실패');
    }
  };

  const handleDeleteLocation = async () => {
    try {
      await backendApi.deleteLocation();
      setUserLocation(null);
      setUseLocationFilter(false);
      toast.success('소재지가 삭제되었습니다');
    } catch {
      toast.error('소재지 삭제 실패');
    }
  };

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

      setCnstrtsiteRgnNm(filters.cnstrtsiteRgnNm || '');
      setPriceStart(filters.priceStart || filters.presmptPrceBgn || '');
      setPriceEnd(filters.priceEnd || filters.presmptPrceEnd || '');
      setExcludeClosed(filters.excludeClosed || filters.bidClseExcpYn || 'N');

      if (filters.useLocationFilter !== undefined) {
          setUseLocationFilter(filters.useLocationFilter);
      }
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
    cnstrtsiteRgnNm,
    industries,
    priceStart,
    priceEnd,
    excludeClosed,
    useLocationFilter,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!date?.from || !date?.to) {
      toast.error('조회 기간을 선택해주세요');
      return;
    }

    if (useLocationFilter && !userLocation) {
      toast.error('소재지를 먼저 등록해주세요');
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
      prtcptLmtRgnNm: (!useLocationFilter && regions.length > 0) ? regions.join(',') : undefined,
      cnstrtsiteRgnNm: cnstrtsiteRgnNm.trim() || undefined,
      indstrytyNm: industries.length > 0 ? industries.join(',') : undefined,
      presmptPrceBgn: priceStart || undefined,
      presmptPrceEnd: priceEnd || undefined,
      bidClseExcpYn: excludeClosed || undefined,
      useLocationFilter: useLocationFilter || undefined,
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
          {/* 소재지 등록 영역 */}
          <div className="flex items-center gap-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
            <MapPin className="h-5 w-5 text-blue-600 shrink-0" />
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className="text-sm font-medium text-blue-800 shrink-0">소재지:</span>
              {userLocation ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-blue-900 font-semibold">{userLocation.location_name}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    onClick={() => {
                      setLocationInput(userLocation.location_name);
                      setIsLocationDialogOpen(true);
                    }}
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
                    onClick={handleDeleteLocation}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsLocationDialogOpen(true)}
                >
                  소재지 등록
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Switch
                id="locationFilter"
                checked={useLocationFilter}
                onCheckedChange={(checked) => {
                  if (checked && !userLocation) {
                    toast.error('소재지를 먼저 등록해주세요');
                    return;
                  }
                  setUseLocationFilter(checked);
                }}
              />
              <Label htmlFor="locationFilter" className="text-sm text-blue-800 cursor-pointer whitespace-nowrap">
                소재지 기준 참가가능지역 필터링
              </Label>
            </div>
          </div>

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

            <div className="space-y-2">
              <Label>조회 기간</Label>
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
                    <CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
                    {date?.from ? (
                      date.to ? (
                        <span className="truncate">
                          {format(date.from, "yy.MM.dd")} ~ {format(date.to, "yy.MM.dd")}
                        </span>
                      ) : (
                        format(date.from, "yy.MM.dd")
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
                    defaultMonth={date?.from}
                    selected={date}
                    onSelect={setDate}
                    numberOfMonths={1}
                    locale={ko}
                  />
                  <div className="border-t px-4 py-2 flex justify-between text-xs">
                    <div>
                      <span className="text-muted-foreground">시작일: </span>
                      <span className="font-medium">{date?.from ? format(date.from, 'yyyy.MM.dd') : '-'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">종료일: </span>
                      <span className="font-medium">{date?.to ? format(date.to, 'yyyy.MM.dd') : '-'}</span>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label>참가제한지역 (선택){useLocationFilter && <span className="text-xs text-blue-600 ml-1">- 소재지 필터</span>}</Label>
              <TagInput
                placeholder="예: 서울특별시"
                tags={regions}
                onChange={setRegions}
                disabled={useLocationFilter}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="cnstrtsiteRgnNm">현장 (선택)</Label>
              <Input
                id="cnstrtsiteRgnNm"
                type="text"
                placeholder="예: 서울"
                value={cnstrtsiteRgnNm}
                onChange={(e) => setCnstrtsiteRgnNm(e.target.value)}
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

            <div className="space-y-2">
              <Label htmlFor="bidClseExcpYn">입찰마감 제외</Label>
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

        {/* 검색 조건 저장 다이얼로그 */}
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

        {/* 소재지 등록/수정 다이얼로그 */}
        <Dialog open={isLocationDialogOpen} onOpenChange={setIsLocationDialogOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>소재지 등록</DialogTitle>
                </DialogHeader>
                <div className="py-4 space-y-2">
                    <Label htmlFor="locationInput">소재지</Label>
                    <Input
                        id="locationInput"
                        value={locationInput}
                        onChange={(e) => setLocationInput(e.target.value)}
                        placeholder="예: 경기도 성남시"
                    />
                    <p className="text-xs text-muted-foreground">
                        소재지를 기준으로 참가가능지역을 자동 필터링합니다.<br />
                        예: "경기도 성남시" 등록 시 → 전체, 경기도, 경기도 성남시 지역 공고가 필터링됩니다.
                    </p>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => setIsLocationDialogOpen(false)}>취소</Button>
                    <Button onClick={handleSaveLocation}>저장</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
