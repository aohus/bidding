import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { backendApi } from '@/lib/backendApi';
import { parseDt } from '@/lib/bookmarkHelpers';
import {
  BookmarkWithStatus,
  BookmarkListMeta,
  BookmarkSortField,
  BookmarkSortDir,
  BookmarkOpengStatus,
} from '@/types/bid';

const PAGE_SIZE = 20;
const RESULT_REFRESH_WINDOW_MINUTES = 30;
const RESULT_REFRESH_CONCURRENCY = 3;
const VALID_SORT_FIELDS: BookmarkSortField[] = ['openg_dt', 'bid_close_dt', 'created_at', 'rank'];
const VALID_SORT_DIRS: BookmarkSortDir[] = ['asc', 'desc'];
const VALID_OPENG_STATUSES: BookmarkOpengStatus[] = ['all', 'today', 'upcoming', 'waiting', 'completed'];

type TabKey = 'bid_completed' | 'interested';
const VALID_TABS: TabKey[] = ['bid_completed', 'interested'];

interface TabState {
  page: number;
  sortField: BookmarkSortField;
  sortDir: BookmarkSortDir;
  opengStatus: BookmarkOpengStatus;
}

interface TabData {
  items: BookmarkWithStatus[];
  meta: BookmarkListMeta | null;
  loading: boolean;
}

const DEFAULT_STATE: TabState = {
  page: 1,
  sortField: 'openg_dt',
  sortDir: 'desc',
  opengStatus: 'all',
};

function readFromParams(params: URLSearchParams, tab: TabKey): TabState {
  if (params.get('tab') !== tab) return { ...DEFAULT_STATE };
  const rawSort = params.get('sort') as BookmarkSortField | null;
  const rawDir = params.get('dir') as BookmarkSortDir | null;
  const rawFilter = params.get('filter') as BookmarkOpengStatus | null;

  return {
    page: Math.max(1, Number(params.get('page')) || 1),
    sortField: rawSort && VALID_SORT_FIELDS.includes(rawSort) ? rawSort : 'openg_dt',
    sortDir: rawDir && VALID_SORT_DIRS.includes(rawDir) ? rawDir : 'desc',
    opengStatus: rawFilter && VALID_OPENG_STATUSES.includes(rawFilter) ? rawFilter : 'all',
  };
}

const EMPTY_DATA: TabData = { items: [], meta: null, loading: true };

export function useBookmarkList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const loadSeq = useRef(0);
  const isFirstRender = useRef(true);

  const rawTab = searchParams.get('tab') as TabKey | null;
  const activeTab: TabKey = rawTab && VALID_TABS.includes(rawTab) ? rawTab : 'bid_completed';

  const [tabStates, setTabStates] = useState<Record<TabKey, TabState>>({
    bid_completed: readFromParams(searchParams, 'bid_completed'),
    interested: readFromParams(searchParams, 'interested'),
  });

  const [tabData, setTabData] = useState<Record<TabKey, TabData>>({
    bid_completed: { ...EMPTY_DATA },
    interested: { ...EMPTY_DATA },
  });

  const [refetchSeq, setRefetchSeq] = useState<Record<TabKey, number>>({
    bid_completed: 0,
    interested: 0,
  });

  const state = tabStates[activeTab];
  const data = tabData[activeTab];

  // Sync URL when active tab state changes (skip on first render to avoid overwriting URL)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const p = new URLSearchParams();
    p.set('tab', activeTab);
    p.set('page', String(state.page));
    p.set('sort', state.sortField);
    p.set('dir', state.sortDir);
    if (state.opengStatus !== 'all') p.set('filter', state.opengStatus);
    setSearchParams(p, { replace: true });
  }, [activeTab, state.page, state.sortField, state.sortDir, state.opengStatus]);

  // Fetch when state changes
  useEffect(() => {
    const seq = ++loadSeq.current;

    setTabData(prev => ({
      ...prev,
      [activeTab]: { ...prev[activeTab], loading: true },
    }));

    backendApi
      .getBookmarks({
        status: activeTab,
        page: state.page,
        pageSize: PAGE_SIZE,
        sortField: state.sortField,
        sortDir: state.sortDir,
        opengStatus: state.opengStatus,
      })
      .then(result => {
        if (seq !== loadSeq.current) return;
        setTabData(prev => ({
          ...prev,
          [activeTab]: { items: result.items, meta: result.meta, loading: false },
        }));
        // Trigger background waiting-results refresh for bid_completed
        if (activeTab === 'bid_completed') {
          refreshWaiting(result.items, seq);
        }
      })
      .catch(() => {
        if (seq !== loadSeq.current) return;
        setTabData(prev => ({
          ...prev,
          [activeTab]: { ...prev[activeTab], loading: false },
        }));
        toast.error('목록을 불러오는데 실패했습니다');
      });
  }, [activeTab, state.page, state.sortField, state.sortDir, state.opengStatus, refetchSeq[activeTab]]);

  async function refreshWaiting(items: BookmarkWithStatus[], seq: number) {
    const now = new Date();
    const threshold = new Date(now.getTime() + RESULT_REFRESH_WINDOW_MINUTES * 60 * 1000);
    const waiting = items.filter(b => {
      if (b.openg_completed) return false;
      const openg = parseDt(b.openg_dt);
      return openg !== null && openg <= threshold;
    });
    if (!waiting.length) return;

    const results: PromiseSettledResult<Awaited<ReturnType<typeof backendApi.getBidResults>>>[] = [];
    for (let i = 0; i < waiting.length; i += RESULT_REFRESH_CONCURRENCY) {
      const batch = waiting.slice(i, i + RESULT_REFRESH_CONCURRENCY);
      results.push(
        ...(await Promise.allSettled(
          batch.map(b => backendApi.getBidResults(b.bid_notice_no, b.bid_notice_ord || '000'))
        ))
      );
      if (seq !== loadSeq.current) return;
    }
    const hasNew = results.some(r => r.status === 'fulfilled' && r.value.results.length > 0);
    if (!hasNew || seq !== loadSeq.current) return;

    // Re-fetch current page to reflect new results
    backendApi
      .getBookmarks({
        status: 'bid_completed',
        page: tabStates.bid_completed.page,
        pageSize: PAGE_SIZE,
        sortField: tabStates.bid_completed.sortField,
        sortDir: tabStates.bid_completed.sortDir,
        opengStatus: tabStates.bid_completed.opengStatus,
      })
      .then(result => {
        if (seq !== loadSeq.current) return;
        setTabData(prev => ({
          ...prev,
          bid_completed: { items: result.items, meta: result.meta, loading: false },
        }));
      })
      .catch(() => {
        if (seq !== loadSeq.current) return;
        toast.error('개찰결과 갱신에 실패했습니다');
      });
  }

  const setTab = useCallback((tab: string) => {
    const t = tab as TabKey;
    const s = tabStates[t];
    const p = new URLSearchParams();
    p.set('tab', t);
    p.set('page', String(s.page));
    p.set('sort', s.sortField);
    p.set('dir', s.sortDir);
    if (s.opengStatus !== 'all') p.set('filter', s.opengStatus);
    setSearchParams(p, { replace: false });
  }, [tabStates, setSearchParams]);

  const setPage = useCallback((page: number) => {
    setTabStates(prev => ({ ...prev, [activeTab]: { ...prev[activeTab], page } }));
  }, [activeTab]);

  const setSort = useCallback((field: BookmarkSortField) => {
    setTabStates(prev => {
      const cur = prev[activeTab];
      return {
        ...prev,
        [activeTab]: {
          ...cur,
          sortField: field,
          sortDir: cur.sortField === field ? (cur.sortDir === 'asc' ? 'desc' : 'asc') : 'asc',
          page: 1,
        },
      };
    });
  }, [activeTab]);

  const setOpengStatus = useCallback((s: BookmarkOpengStatus) => {
    setTabStates(prev => ({
      ...prev,
      [activeTab]: { ...prev[activeTab], opengStatus: s, page: 1 },
    }));
  }, [activeTab]);

  const refetch = useCallback(() => {
    setRefetchSeq(prev => ({ ...prev, [activeTab]: prev[activeTab] + 1 }));
  }, [activeTab]);

  return {
    activeTab,
    setTab,
    items: data.items,
    meta: data.meta,
    loading: data.loading,
    state,
    setPage,
    setSort,
    setOpengStatus,
    refetch,
  };
}
