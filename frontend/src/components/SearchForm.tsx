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

interface SearchFormProps {
  onSearch: (params: BidSearchParams, page?: number) => void;
  isLoading: boolean;
  initialValues?: BidSearchParams | null;
}

export default function SearchForm({ onSearch, isLoading, initialValues }: SearchFormProps) {
  const [inqryDiv, setInqryDiv] = useState<'1' | '2'>('1');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [regionName, setRegionName] = useState('');
  const [industryName, setIndustryName] = useState('');
  const [priceStart, setPriceStart] = useState('');
  const [priceEnd, setPriceEnd] = useState('');
  const [excludeClosed, setExcludeClosed] = useState<'Y' | 'N'>('N');

  // Load saved preferences or initial values on mount/update
  useEffect(() => {
    if (initialValues) {
      setInqryDiv(initialValues.inqryDiv);
      if (initialValues.inqryBgnDt && initialValues.inqryBgnDt.length >= 8) {
        const y = initialValues.inqryBgnDt.substring(0, 4);
        const m = initialValues.inqryBgnDt.substring(4, 6);
        const d = initialValues.inqryBgnDt.substring(6, 8);
        setStartDate(`${y}-${m}-${d}`);
      }
      if (initialValues.inqryEndDt && initialValues.inqryEndDt.length >= 8) {
        const y = initialValues.inqryEndDt.substring(0, 4);
        const m = initialValues.inqryEndDt.substring(4, 6);
        const d = initialValues.inqryEndDt.substring(6, 8);
        setEndDate(`${y}-${m}-${d}`);
      }
      setRegionName(initialValues.prtcptLmtRgnNm || '');
      setIndustryName(initialValues.indstrytyNm || '');
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
        if (conditions.startDate) setStartDate(conditions.startDate as string);
        if (conditions.endDate) setEndDate(conditions.endDate as string);
        if (conditions.regionName) setRegionName(conditions.regionName as string);
        if (conditions.industryName) setIndustryName(conditions.industryName as string);
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
        startDate,
        endDate,
        regionName,
        industryName,
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

    if (!startDate || !endDate) {
      toast.error('시작일과 종료일을 입력해주세요');
      return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);

    if (start > end) {
      toast.error('시작일이 종료일보다 늦을 수 없습니다');
      return;
    }

    const formatDateTime = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}${month}${day}0000`;
    };

    const params: BidSearchParams = {
      inqryDiv,
      inqryBgnDt: formatDateTime(start),
      inqryEndDt: formatDateTime(end),
      prtcptLmtRgnNm: regionName || undefined,
      indstrytyNm: industryName || undefined,
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

            <div className="space-y-2">
              <Label htmlFor="startDate">시작일</Label>
              <Input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="endDate">종료일</Label>
              <Input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="regionName">참가제한지역명 (선택)</Label>
              <Input
                id="regionName"
                type="text"
                placeholder="예: 서울특별시"
                value={regionName}
                onChange={(e) => setRegionName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="industryName">업종명 (선택)</Label>
              <Input
                id="industryName"
                type="text"
                placeholder="예: 토목건축"
                value={industryName}
                onChange={(e) => setIndustryName(e.target.value)}
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
