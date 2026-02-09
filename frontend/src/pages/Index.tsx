import { useState, useEffect } from 'react';
import { BidSearchParams, BidItem, BidAValueItem } from '@/types/bid';
import SearchForm from '@/components/SearchForm';
import BidTable from '@/components/BidTable';
import BidCalculator from '@/components/BidCalculator';
import AuthForm from '@/components/AuthForm';
import Header from '@/components/Header';
import { backendApi } from '@/lib/backendApi';
import { AuthService } from '@/lib/auth';
import { toast } from 'sonner';
import { useSearchState } from '@/hooks/useSearchState';


export default function Index() {
  // --- 인증 및 기본 상태 ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Custom Hook for Search State (LocalStorage persistence)
  const {
    searchParams: currentSearchParams,
    setSearchParams: setCurrentSearchParams,
    bids,
    setBids,
    totalCount,
    setTotalCount,
    currentPage,
    setCurrentPage,
    isLoaded
  } = useSearchState();

  const [isLoading, setIsLoading] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false); // A값 조회 전용 로딩

  // --- 선택된 공고 및 계산기 상태 ---
  const [selectedBid, setSelectedBid] = useState<BidItem | null>(null);
  const [selectedAValue, setSelectedAValue] = useState<BidAValueItem | null>(null);
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);
  
  // --- 페이지네이션 상태 (Derived) ---
  const numOfRows = currentSearchParams?.numOfRows || 100;
  const totalPages = Math.ceil(totalCount / numOfRows) || 0;

  // 인증 체크
  useEffect(() => {
    setIsAuthenticated(AuthService.isAuthenticated());
  }, []);

  // 초기 자동 검색 및 데이터 복원 처리
  useEffect(() => {
    if (!isLoaded) return;

    // 저장된 검색 조건이 없으면 기본값(오늘자 개찰일시)으로 검색 수행
    if (!currentSearchParams) {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      
      const defaultParams: BidSearchParams = {
        inqryDiv: '2', // 개찰일시
        inqryBgnDt: `${year}${month}${day}0000`,
        inqryEndDt: `${year}${month}${day}2359`,
        numOfRows: 100,
        pageNo: 1
      };
      
      handleSearch(defaultParams);
    }
    // 저장된 검색 조건이 있으면, useSearchState가 이미 bids와 totalCount를 복원했으므로 추가 동작 불필요
    // 단, 결과가 비어있는데 검색 조건만 있는 경우(예: 오류로 결과 저장 안됨) 재검색을 원한다면 로직 추가 가능
    // 현재는 '상태 복원'에 충실하여 API 재호출 하지 않음 (불필요한 트래픽 방지)
  }, [isLoaded]);

  /**
   * [1] 공고 검색 핸들러
   */
  const handleSearch = async (params: BidSearchParams, page: number = 1) => {
    setIsLoading(true);
    try {
      const searchParams = {
        ...params,
        pageNo: page,
        numOfRows: 100,
      };

      const response = await backendApi.searchBids(searchParams);
      const items = response.response.body.items || [];
      const total = response.response.body.totalCount || 0;
      
      setBids(items);
      setTotalCount(total);
      setCurrentPage(page);
      setCurrentSearchParams(params);
      
      if (items.length === 0) {
        toast.info('검색 결과가 없습니다');
      } else {
        toast.success(`${total.toLocaleString()}개의 입찰 공고를 찾았습니다 (${page}/${Math.ceil(total / 100)} 페이지)`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '검색 실패');
      setBids([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * [2] 페이지 변경 핸들러
   */
  const handlePageChange = (page: number) => {
    if (currentSearchParams && page >= 1 && page <= totalPages) {
      handleSearch(currentSearchParams, page);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  /**
   * [3] 투찰 계산 버튼 핸들러 (A값 실시간 조회 로직 포함)
   * 명세서상 getBidPblancListBidPrceCalclAInfo 오퍼레이션을 호출합니다.
   */
  const handleCalculate = async (bid: BidItem) => {
    setIsCalculating(true);
    const toastId = toast.loading('공고의 A값(국민연금 등 고정비용)을 분석 중입니다...');
    
    try {
      // 공고 유형 판별 (공사: cnstwk, 용역: servc)
      // bidClsfcNo: 1(공사), 3(용역), 5(물품) 등
      // 또는 주공종명(mainCnsttyNm) 존재 여부로 판별
      const bidType = (bid.mainCnsttyNm || bid.cnstrtsiteRgnNm) ? 'cnstwk' : 'servc';
      
      // API를 통해 해당 공고번호(bidNtceNo)의 A값 정보를 가져옴
      const aValueItem = await backendApi.getBidAValue(bid.bidNtceNo, bidType);
      
      setSelectedAValue(aValueItem);
      setSelectedBid(bid);
      setIsCalculatorOpen(true);
      
      if (aValueItem) {
        toast.success(`A값이 적용되었습니다.`, { id: toastId });
      } else {
        toast.info('A값이 명시되지 않은 공고입니다. 일반 산식으로 진행합니다.', { id: toastId });
      }
    } catch (error) {
      console.error('A값 조회 오류:', error);
      toast.error('A값 정보를 가져오지 못했습니다. 기본값 0으로 진행합니다.', { id: toastId });
      
      // 오류 시에도 계산기는 열어주되, A값은 0으로 설정
      setSelectedAValue(0);
      setSelectedBid(bid);
      setIsCalculatorOpen(true);
    } finally {
      setIsCalculating(false);
    }
  };

  /**
   * [4] 인증 및 로그아웃 핸들러
   */
  const handleAuthSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setBids([]);
    setCurrentPage(1);
    setTotalCount(0);
    setCurrentSearchParams(null);
    toast.success('로그아웃되었습니다');
  };

  // 미인증 시 로그인 폼 표시
  if (!isAuthenticated) {
    return <AuthForm onSuccess={handleAuthSuccess} />;
  }

  // 로딩 전에는 아무것도 보여주지 않음 (깜빡임 방지)
  if (!isLoaded) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Header onLogout={handleLogout} />
      
      <main className="container mx-auto px-4 py-8">
        <div className="space-y-6">
          {/* 검색 필터 영역 */}
          {/* SearchForm에 초기값을 전달해야 함. 현재 SearchForm은 내부 상태를 가짐. 
              SearchForm을 수정하여 initialValues를 받도록 하거나, currentSearchParams를 전달해야 함.
              SearchForm 코드를 확인해야 함. */}
          <SearchForm onSearch={handleSearch} isLoading={isLoading} initialValues={currentSearchParams} />
          
          {/* 검색 결과 테이블 영역 */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-800">검색 결과</h2>
                {totalCount > 0 && (
                  <span className="text-sm text-gray-500">
                    전체 <strong>{totalCount.toLocaleString()}</strong>건
                  </span>
                )}
              </div>

              <BidTable 
                bids={bids} 
                onCalculate={handleCalculate} // 수정된 핸들러
                currentPage={currentPage}
                totalPages={totalPages}
                totalCount={totalCount}
                onPageChange={handlePageChange}
                isLoading={isLoading || isCalculating}
              />
            </div>
          </div>
        </div>
      </main>

      {/* 투찰 전략 계산기 모달 */}
      <BidCalculator
        bid={selectedBid}
        aValueItem={selectedAValue} // API에서 받아온 A값 전달
        isOpen={isCalculatorOpen}
        onClose={() => setIsCalculatorOpen(false)}
      />
    </div>
  );
}