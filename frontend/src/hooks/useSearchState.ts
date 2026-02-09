import { useState, useEffect } from 'react';
import { BidSearchParams, BidItem } from '@/types/bid';

const STORAGE_KEYS = {
  SEARCH_PARAMS: 'searchParams',
  SEARCH_RESULTS: 'searchResults',
  TOTAL_COUNT: 'totalCount',
  PAGE: 'page'
};

export function useSearchState() {
  const [searchParams, setSearchParamsState] = useState<BidSearchParams | null>(null);
  const [bids, setBidsState] = useState<BidItem[]>([]);
  const [totalCount, setTotalCountState] = useState(0);
  const [currentPage, setCurrentPageState] = useState(1);
  const [isLoaded, setIsLoaded] = useState(false);

  // Initialize from localStorage
  useEffect(() => {
    try {
      const storedParams = localStorage.getItem(STORAGE_KEYS.SEARCH_PARAMS);
      const storedResults = localStorage.getItem(STORAGE_KEYS.SEARCH_RESULTS);
      const storedTotal = localStorage.getItem(STORAGE_KEYS.TOTAL_COUNT);
      const storedPage = localStorage.getItem(STORAGE_KEYS.PAGE);

      if (storedParams) setSearchParamsState(JSON.parse(storedParams));
      if (storedResults) setBidsState(JSON.parse(storedResults));
      if (storedTotal) setTotalCountState(parseInt(storedTotal, 10));
      if (storedPage) setCurrentPageState(parseInt(storedPage, 10));
    } catch (e) {
      console.error('Failed to load search state from localStorage', e);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  const setSearchParams = (params: BidSearchParams | null) => {
    setSearchParamsState(params);
    if (params) {
      localStorage.setItem(STORAGE_KEYS.SEARCH_PARAMS, JSON.stringify(params));
    } else {
      localStorage.removeItem(STORAGE_KEYS.SEARCH_PARAMS);
    }
  };

  const setBids = (items: BidItem[]) => {
    setBidsState(items);
    localStorage.setItem(STORAGE_KEYS.SEARCH_RESULTS, JSON.stringify(items));
  };

  const setTotalCount = (count: number) => {
    setTotalCountState(count);
    localStorage.setItem(STORAGE_KEYS.TOTAL_COUNT, count.toString());
  };

  const setCurrentPage = (page: number) => {
    setCurrentPageState(page);
    localStorage.setItem(STORAGE_KEYS.PAGE, page.toString());
  };

  return {
    searchParams,
    setSearchParams,
    bids,
    setBids,
    totalCount,
    setTotalCount,
    currentPage,
    setCurrentPage,
    isLoaded
  };
}
