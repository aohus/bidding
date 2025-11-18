import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BidSearchParams } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Save, Download } from 'lucide-react';

interface SearchFormProps {
  onSearch: (params: BidSearchParams) => void;
  isLoading: boolean;
}

export default function SearchForm({ onSearch, isLoading }: SearchFormProps) {
  const [inqryDiv, setInqryDiv] = useState<'1' | '2'>('1');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [region, setRegion] = useState('');

  // Load saved preferences on mount
  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    try {
      const preference = await backendApi.getPreference();
      if (preference && preference.search_conditions) {
        const conditions = preference.search_conditions;
        if (conditions.inqryDiv) setInqryDiv(conditions.inqryDiv);
        if (conditions.startDate) setStartDate(conditions.startDate);
        if (conditions.endDate) setEndDate(conditions.endDate);
        if (conditions.region) setRegion(conditions.region);
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
        region,
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
      prtcptLmtRgnCd: region || undefined,
      numOfRows: 100,
      pageNo: 1,
    };

    onSearch(params);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>입찰 공고 검색</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
              <Label htmlFor="region">지역 (선택)</Label>
              <Input
                id="region"
                type="text"
                placeholder="예: 11 (서울)"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
              />
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