import { useState } from 'react';
import { toast } from 'sonner';
import SearchForm from '@/components/SearchForm';
import BidTable from '@/components/BidTable';
import BidCalculator from '@/components/BidCalculator';
import { searchBids } from '@/lib/api';
import { BidItem } from '@/types/bid';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Settings } from 'lucide-react';

interface SearchParams {
  inqryDiv: '1' | '2';
  inqryBgnDt: string;
  inqryEndDt: string;
  prtcptLmtRgnCd?: string;
  presmptPrceBgn?: string;
  presmptPrceEnd?: string;
}

export default function Index() {
  const [serviceKey, setServiceKey] = useState<string>('');
  const [isKeySet, setIsKeySet] = useState<boolean>(false);
  const [bids, setBids] = useState<BidItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [selectedBid, setSelectedBid] = useState<BidItem | null>(null);
  const [isCalculatorOpen, setIsCalculatorOpen] = useState<boolean>(false);
  const [totalCount, setTotalCount] = useState<number>(0);

  const handleSetKey = () => {
    if (!serviceKey.trim()) {
      toast.error('API 키를 입력해주세요.');
      return;
    }
    setIsKeySet(true);
    toast.success('API 키가 설정되었습니다.');
  };

  const handleSearch = async (params: SearchParams) => {
    if (!serviceKey) {
      toast.error('먼저 API 키를 설정해주세요.');
      return;
    }

    setIsLoading(true);
    setBids([]);

    try {
      const response = await searchBids({
        ...params,
        ServiceKey: serviceKey,
        numOfRows: 50,
        pageNo: 1,
      });

      const items = response.response.body.items || [];
      setBids(items);
      setTotalCount(response.response.body.totalCount);

      if (items.length === 0) {
        toast.info('검색 결과가 없습니다.');
      } else {
        toast.success(`${items.length}건의 입찰공고를 찾았습니다.`);
      }
    } catch (error) {
      console.error('검색 오류:', error);
      toast.error('검색 중 오류가 발생했습니다. API 키와 검색 조건을 확인해주세요.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCalculate = (bid: BidItem) => {
    setSelectedBid(bid);
    setIsCalculatorOpen(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="container mx-auto py-8 px-4">
        <div className="mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-2">
            나라장터 입찰공고 검색 시스템
          </h1>
          <p className="text-muted-foreground">공사 입찰 정보를 검색하고 최적의 투찰 가격을 계산하세요</p>
        </div>

        {!isKeySet ? (
          <Card className="max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Settings className="mr-2 h-5 w-5" />
                API 키 설정
              </CardTitle>
              <CardDescription>나라장터 API 서비스 키를 입력해주세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="serviceKey">Service Key</Label>
                <Input
                  id="serviceKey"
                  type="text"
                  placeholder="API 서비스 키를 입력하세요"
                  value={serviceKey}
                  onChange={(e) => setServiceKey(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSetKey()}
                />
              </div>
              <Button onClick={handleSetKey} className="w-full">
                API 키 설정
              </Button>
              <p className="text-xs text-muted-foreground">
                * API 키는 공공데이터포털(data.go.kr)에서 발급받을 수 있습니다.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            <SearchForm onSearch={handleSearch} isLoading={isLoading} />

            {totalCount > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  총 <span className="font-semibold text-foreground">{totalCount}</span>건의 입찰공고 (
                  <span className="font-semibold text-foreground">{bids.length}</span>건 표시)
                </p>
                <Button variant="outline" size="sm" onClick={() => setIsKeySet(false)}>
                  <Settings className="mr-2 h-4 w-4" />
                  API 키 변경
                </Button>
              </div>
            )}

            <Card>
              <CardHeader>
                <CardTitle>검색 결과</CardTitle>
                <CardDescription>입찰공고 목록</CardDescription>
              </CardHeader>
              <CardContent>
                <BidTable bids={bids} onCalculate={handleCalculate} />
              </CardContent>
            </Card>
          </div>
        )}

        <BidCalculator bid={selectedBid} isOpen={isCalculatorOpen} onClose={() => setIsCalculatorOpen(false)} />
      </div>
    </div>
  );
}