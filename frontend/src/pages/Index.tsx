import { useState, useEffect, useCallback } from 'react';
import { BidSearchParams, BidItem, BidAValueItem } from '@/types/bid';
import SearchForm from '@/components/SearchForm';
import BidTable, { BookmarkInfo } from '@/components/BidTable';
import BidCalculator from '@/components/BidCalculator';
import AuthForm from '@/components/AuthForm';
import Header from '@/components/Header';
import { backendApi } from '@/lib/backendApi';
import { AuthService } from '@/lib/auth';
import { toast } from 'sonner';
import { useSearchState } from '@/hooks/useSearchState';


export default function Index() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

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
  const [isCalculating, setIsCalculating] = useState(false);

  const [selectedBid, setSelectedBid] = useState<BidItem | null>(null);
  const [selectedAValue, setSelectedAValue] = useState<BidAValueItem | null>(null);
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);

  const [numOfRows, setNumOfRows] = useState(100);
  const [orderBy, setOrderBy] = useState<string | undefined>();
  const [orderDir, setOrderDir] = useState<'asc' | 'desc' | undefined>();
  const [bookmarkMap, setBookmarkMap] = useState<Map<string, BookmarkInfo>>(new Map());

  const totalPages = Math.ceil(totalCount / numOfRows) || 0;

  useEffect(() => {
    setIsAuthenticated(AuthService.isAuthenticated());
    AuthService.setOnExpired(() => {
      setIsAuthenticated(false);
      setBids([]);
      setCurrentPage(1);
      setTotalCount(0);
      setCurrentSearchParams(null);
    });
    return () => AuthService.setOnExpired(null);
  }, [setBids, setCurrentPage, setTotalCount, setCurrentSearchParams]);

  // 북마크 목록 로드
  const loadBookmarks = useCallback(async () => {
    try {
      const bookmarks = await backendApi.getBookmarks();
      const map = new Map<string, BookmarkInfo>();
      for (const b of bookmarks) {
        map.set(b.bid_notice_no, { status: b.status, bookmarkId: b.bookmark_id });
      }
      setBookmarkMap(map);
    } catch {
      // 실패 시 무시
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadBookmarks();
    // 대시보드에서 돌아왔을 때 북마크 동기화
    const onVisible = () => {
      if (document.visibilityState === 'visible') loadBookmarks();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [isAuthenticated, loadBookmarks]);

  const handleBookmarkToggle = async (bid: BidItem, status: 'interested' | 'bid_completed') => {
    const existing = bookmarkMap.get(bid.bidNtceNo);

    try {
      if (existing?.status === status) {
        // 같은 상태 다시 클릭 → 취소 (삭제)
        await backendApi.deleteBookmark(existing.bookmarkId);
        toast.success(status === 'interested' ? '관심공고 해제했습니다' : '투찰완료 해제했습니다');
      } else if (existing) {
        // 다른 상태로 변경 (interested ↔ bid_completed)
        await backendApi.updateBookmark(existing.bookmarkId, { status });
        toast.success(status === 'interested' ? '관심공고로 변경했습니다' : '투찰완료로 변경했습니다');
      } else {
        // 새로 생성
        await backendApi.createBookmark(bid.bidNtceNo, bid.bidNtceNm, {
          status,
          bid_notice_ord: bid.bidNtceOrd,
        });
        toast.success(status === 'interested' ? '관심공고로 저장했습니다' : '투찰완료로 저장했습니다');
      }
      await loadBookmarks();
    } catch (error: any) {
      if (error.message?.includes('already exists')) {
        toast.error('이미 저장된 공고입니다');
      } else {
        toast.error('저장에 실패했습니다');
      }
    }
  };

  const handleSearch = useCallback(async (
    params: BidSearchParams,
    page: number = 1,
    opts?: { rows?: number; sortBy?: string; sortDir?: 'asc' | 'desc' }
  ) => {
    const rows = opts?.rows ?? numOfRows;
    const sort = opts?.sortBy ?? orderBy;
    const dir = opts?.sortDir ?? orderDir;

    setIsLoading(true);
    try {
      const searchParams = {
        ...params,
        pageNo: page,
        numOfRows: rows,
        orderBy: sort,
        orderDir: dir,
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
        toast.success(`${total.toLocaleString()}개의 입찰 공고를 찾았습니다 (${page}/${Math.ceil(total / rows)} 페이지)`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '검색 실패');
      setBids([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  }, [setBids, setTotalCount, setCurrentPage, setCurrentSearchParams, numOfRows, orderBy, orderDir]);

  // 초기 자동 검색: 저장된 기본 검색 조건 + 오늘 날짜
  useEffect(() => {
    if (!isLoaded || !isAuthenticated) return;
    if (currentSearchParams) return; // 이미 검색 상태가 있으면 스킵

    const initSearch = async () => {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');

      let defaultParams: BidSearchParams = {
        inqryDiv: '2',
        inqryBgnDt: `${year}${month}${day}0000`,
        inqryEndDt: `${year}${month}${day}2359`,
        numOfRows: 100,
        pageNo: 1,
      };

      // 저장된 기본 검색 조건이 있으면 날짜를 오늘로 덮어쓰고 사용
      try {
        const preference = await backendApi.getPreference();
        if (preference?.search_conditions) {
          const saved = preference.search_conditions;
          defaultParams = {
            ...defaultParams,
            inqryDiv: (saved.inqryDiv as '1' | '2') || defaultParams.inqryDiv,
            indstrytyNm: (saved.industries as string[])?.join(',') || undefined,
            presmptPrceBgn: (saved.priceStart as string) || undefined,
            presmptPrceEnd: (saved.priceEnd as string) || undefined,
            bidClseExcpYn: (saved.excludeClosed as 'Y' | 'N') || undefined,
            useLocationFilter: (saved.useLocationFilter as boolean) || undefined,
          };
        }
      } catch {
        // 기본 검색 조건 없으면 무시
      }

      handleSearch(defaultParams);
    };

    initSearch();
  }, [isLoaded, isAuthenticated]);

  const handlePageChange = (page: number) => {
    if (currentSearchParams && page >= 1 && page <= totalPages) {
      handleSearch(currentSearchParams, page);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleNumOfRowsChange = (rows: number) => {
    setNumOfRows(rows);
    if (currentSearchParams) {
      handleSearch(currentSearchParams, 1, { rows });
    }
  };

  const handleSort = (field: string) => {
    let newDir: 'asc' | 'desc' = 'desc';
    if (orderBy === field) {
      newDir = orderDir === 'desc' ? 'asc' : 'desc';
    }
    setOrderBy(field);
    setOrderDir(newDir);
    if (currentSearchParams) {
      handleSearch(currentSearchParams, 1, { sortBy: field, sortDir: newDir });
    }
  };

  /**
   * 입찰공고명 클릭 핸들러 - A값 조회 후 상세 팝업 표시
   */
  const handleBidClick = async (bid: BidItem) => {
    setIsCalculating(true);
    const toastId = toast.loading('공고 상세 정보를 분석 중입니다...');

    try {
      const bidType = (bid.mainCnsttyNm || bid.cnstrtsiteRgnNm) ? 'cnstwk' : 'servc';
      const aValueItem = await backendApi.getBidAValue(bid.bidNtceNo, bidType);

      // bssamt가 없으면 백엔드가 공고 API로 bid_notices를 갱신했을 수 있음
      // → bid detail을 다시 fetch하여 asignBdgtAmt 확보
      const hasBssamt = aValueItem?.bssamt && aValueItem.bssamt.trim() !== '' && aValueItem.bssamt !== '0';
      let finalBid = bid;
      if (!hasBssamt) {
        const refreshed = await backendApi.getBidDetail(bid.bidNtceNo, bid.bidNtceOrd || '000');
        if (refreshed) {
          finalBid = refreshed;
        }
      }

      setSelectedAValue(aValueItem);
      setSelectedBid(finalBid);
      setIsCalculatorOpen(true);

      if (aValueItem) {
        toast.success('A값이 적용되었습니다.', { id: toastId });
      } else {
        toast.info('A값이 명시되지 않은 공고입니다. 일반 산식으로 진행합니다.', { id: toastId });
      }
    } catch (error) {
      toast.error('A값 정보를 가져오지 못했습니다. 기본값 0으로 진행합니다.', { id: toastId });

      setSelectedAValue(null);
      setSelectedBid(bid);
      setIsCalculatorOpen(true);
    } finally {
      setIsCalculating(false);
    }
  };

  const handleAuthSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setBids([]);
    setCurrentPage(1);
    setTotalCount(0);
    setCurrentSearchParams(null);
    setBookmarkMap(new Map());
    toast.success('로그아웃되었습니다');
  };

  if (!isAuthenticated) {
    return <AuthForm onSuccess={handleAuthSuccess} />;
  }

  if (!isLoaded) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Header onLogout={handleLogout} />

      <main className="mx-auto px-4 py-8 max-w-[1800px]">
        <div className="space-y-6">
          <SearchForm onSearch={handleSearch} isLoading={isLoading} initialValues={currentSearchParams} />

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
                onBidClick={handleBidClick}
                currentPage={currentPage}
                totalPages={totalPages}
                totalCount={totalCount}
                onPageChange={handlePageChange}
                isLoading={isLoading || isCalculating}
                numOfRows={numOfRows}
                onNumOfRowsChange={handleNumOfRowsChange}
                orderBy={orderBy}
                orderDir={orderDir}
                onSort={handleSort}
                bookmarkMap={bookmarkMap}
                onBookmarkToggle={handleBookmarkToggle}
              />
            </div>
          </div>
        </div>
      </main>

      <BidCalculator
        bid={selectedBid}
        aValueItem={selectedAValue}
        isOpen={isCalculatorOpen}
        onClose={() => {
          setIsCalculatorOpen(false);
          loadBookmarks();
        }}
      />
    </div>
  );
}
