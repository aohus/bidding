import { useState, useEffect } from 'react';
import { BidSearchParams, BidItem } from '@/types/bid';
import SearchForm from '@/components/SearchForm';
import BidTable from '@/components/BidTable';
import BidCalculator from '@/components/BidCalculator';
import AuthForm from '@/components/AuthForm';
import Header from '@/components/Header';
import { backendApi } from '@/lib/backendApi';
import { AuthService } from '@/lib/auth';
import { toast } from 'sonner';

export default function Index() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [bids, setBids] = useState<BidItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedBid, setSelectedBid] = useState<BidItem | null>(null);
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);

  useEffect(() => {
    setIsAuthenticated(AuthService.isAuthenticated());
  }, []);

  const handleSearch = async (params: BidSearchParams) => {
    setIsLoading(true);
    try {
      const response = await backendApi.searchBids(params);
      const items = response.response.body.items || [];
      setBids(items);
      
      if (items.length === 0) {
        toast.info('검색 결과가 없습니다');
      } else {
        toast.success(`${items.length}개의 입찰 공고를 찾았습니다`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '검색 실패');
      setBids([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCalculate = (bid: BidItem) => {
    setSelectedBid(bid);
    setIsCalculatorOpen(true);
  };

  const handleAuthSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setBids([]);
    toast.success('로그아웃되었습니다');
  };

  if (!isAuthenticated) {
    return <AuthForm onSuccess={handleAuthSuccess} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header onLogout={handleLogout} />
      
      <main className="container mx-auto px-4 py-8">
        <div className="space-y-6">
          <SearchForm onSearch={handleSearch} isLoading={isLoading} />
          
          <div className="bg-white rounded-lg shadow">
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">검색 결과</h2>
              <BidTable bids={bids} onCalculate={handleCalculate} />
            </div>
          </div>
        </div>
      </main>

      <BidCalculator
        bid={selectedBid}
        isOpen={isCalculatorOpen}
        onClose={() => setIsCalculatorOpen(false)}
      />
    </div>
  );
}