import { useState, useEffect, useMemo } from 'react';
import { AuthService } from '@/lib/auth';
import { backendApi } from '@/lib/backendApi';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Star,
  CheckCircle,
  Pencil,
  Trash2,
  LayoutDashboard,
  Trophy,
  ArrowRightLeft,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import { toast } from 'sonner';
import Header from '@/components/Header';
import BidResultDialog from '@/components/BidResultDialog';
import BidCalculator from '@/components/BidCalculator';
import { useNavigate } from 'react-router-dom';
import { BidItem, BidAValueItem, BookmarkWithStatus } from '@/types/bid';

// ── helpers ──

/** "202502101500" → Date */
function parseDt(dt?: string): Date | null {
  if (!dt || dt.length < 12) return null;
  const y = +dt.slice(0, 4), m = +dt.slice(4, 6) - 1, d = +dt.slice(6, 8);
  const h = +dt.slice(8, 10), mi = +dt.slice(10, 12);
  return new Date(y, m, d, h, mi);
}

/** "202502101500" → "02/10 15:00" */
function formatDt(dt?: string) {
  if (!dt || dt.length < 12) return '-';
  return `${dt.slice(4, 6)}/${dt.slice(6, 8)} ${dt.slice(8, 10)}:${dt.slice(10, 12)}`;
}

type OpengStatus = 'today' | 'upcoming' | 'waiting' | 'completed';

function getOpengStatus(b: BookmarkWithStatus, now: Date): OpengStatus {
  const openg = parseDt(b.openg_dt);
  if (!openg) return b.openg_completed ? 'completed' : 'upcoming';

  const isToday =
    openg.getFullYear() === now.getFullYear() &&
    openg.getMonth() === now.getMonth() &&
    openg.getDate() === now.getDate();

  if (b.openg_completed) return 'completed';
  if (isToday) return 'today';
  if (openg > now) return 'upcoming';
  return 'waiting'; // 시간 경과했지만 결과 없음
}

const STATUS_CFG: Record<OpengStatus, { label: string; bg: string; text: string }> = {
  today:     { label: '오늘 개찰', bg: 'bg-orange-100', text: 'text-orange-700' },
  upcoming:  { label: '개찰 전',   bg: 'bg-blue-100',   text: 'text-blue-700' },
  waiting:   { label: '결과 대기', bg: 'bg-yellow-100', text: 'text-yellow-700' },
  completed: { label: '개찰완료',  bg: 'bg-green-100',  text: 'text-green-700' },
};

function formatAmt(amt?: string) {
  if (!amt) return '-';
  const num = parseFloat(amt);
  if (isNaN(num)) return amt;
  if (num >= 100000000) {
    const eok = Math.floor(num / 100000000);
    const man = Math.floor((num % 100000000) / 10000);
    return man > 0 ? `${eok}억 ${man}만` : `${eok}억`;
  }
  if (num >= 10000) return `${Math.floor(num / 10000)}만`;
  return num.toLocaleString();
}

const g2bUrl = (no: string, ord?: string) =>
  `https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoDtl.do?bidno=${no}&bidseq=${ord || '000'}`;

// ── component ──

type BidFilter = 'all' | OpengStatus;
type SortField = 'openg_dt' | 'bid_close_dt' | 'rank';
type SortDir = 'asc' | 'desc';

export default function Dashboard() {
  const navigate = useNavigate();
  const [bookmarks, setBookmarks] = useState<BookmarkWithStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('bid_completed');

  // 투찰완료 tab state
  const [bidFilter, setBidFilter] = useState<BidFilter>('all');
  const [sortField, setSortField] = useState<SortField>('openg_dt');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Dialogs
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedBookmark, setSelectedBookmark] = useState<BookmarkWithStatus | null>(null);
  const [editNotes, setEditNotes] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [bidPriceDialogOpen, setBidPriceDialogOpen] = useState(false);
  const [bidPriceInput, setBidPriceInput] = useState('');
  const [resultDialogOpen, setResultDialogOpen] = useState(false);
  const [resultBidNtceNo, setResultBidNtceNo] = useState<string | null>(null);
  const [resultBidName, setResultBidName] = useState<string>('');

  // BidCalculator popup state
  const [calcBid, setCalcBid] = useState<BidItem | null>(null);
  const [calcAValue, setCalcAValue] = useState<BidAValueItem | null>(null);
  const [calcOpen, setCalcOpen] = useState(false);
  const [calcLoading, setCalcLoading] = useState(false);

  useEffect(() => {
    AuthService.setOnExpired(() => navigate('/'));
    return () => AuthService.setOnExpired(null);
  }, [navigate]);

  useEffect(() => {
    loadBookmarks();
  }, [activeTab]);

  const loadBookmarks = async () => {
    try {
      setLoading(true);
      const data = await backendApi.getBookmarks(activeTab);
      setBookmarks(data);

      // 투찰완료 탭: 개찰 시간 지났는데 결과 없는 항목 자동 조회
      if (activeTab === 'bid_completed') {
        const now = new Date();
        const waitingItems = data.filter((b) => {
          if (b.openg_completed) return false;
          const openg = parseDt(b.openg_dt);
          return openg !== null && openg <= now;
        });

        if (waitingItems.length > 0) {
          const results = await Promise.allSettled(
            waitingItems.map((b) => backendApi.getBidResults(b.bid_notice_no))
          );
          const hasNewResults = results.some(
            (r) => r.status === 'fulfilled' && r.value.results.length > 0
          );
          if (hasNewResults) {
            const freshData = await backendApi.getBookmarks(activeTab);
            setBookmarks(freshData);
          }
        }
      }
    } catch {
      toast.error('목록을 불러오는데 실패했습니다');
    } finally {
      setLoading(false);
    }
  };

  // ── actions ──

  const handleEditClick = (bookmark: BookmarkWithStatus) => {
    setSelectedBookmark(bookmark);
    setEditNotes(bookmark.notes || '');
    setEditDialogOpen(true);
  };

  const handleSaveNotes = async () => {
    if (!selectedBookmark) return;
    try {
      await backendApi.updateBookmark(selectedBookmark.bookmark_id, { notes: editNotes });
      toast.success('메모가 수정되었습니다');
      setEditDialogOpen(false);
      loadBookmarks();
    } catch {
      toast.error('메모 수정에 실패했습니다');
    }
  };

  const handleDeleteClick = (bookmark: BookmarkWithStatus) => {
    setSelectedBookmark(bookmark);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedBookmark) return;
    try {
      await backendApi.deleteBookmark(selectedBookmark.bookmark_id);
      toast.success('삭제되었습니다');
      setDeleteDialogOpen(false);
      loadBookmarks();
    } catch {
      toast.error('삭제에 실패했습니다');
    }
  };

  const handleChangeToBidCompleted = async (bookmark: BookmarkWithStatus) => {
    try {
      await backendApi.updateBookmark(bookmark.bookmark_id, { status: 'bid_completed' });
      toast.success('투찰완료로 변경했습니다');
      loadBookmarks();
    } catch {
      toast.error('변경에 실패했습니다');
    }
  };

  const handleViewResults = (bookmark: BookmarkWithStatus) => {
    setResultBidNtceNo(bookmark.bid_notice_no);
    setResultBidName(bookmark.bid_notice_name);
    setResultDialogOpen(true);
  };

  const handleOpenCalculator = async (bookmark: BookmarkWithStatus) => {
    setCalcLoading(true);
    const toastId = toast.loading('공고 상세 정보를 불러오는 중...');
    try {
      const [bid, aValue] = await Promise.all([
        backendApi.getBidDetail(bookmark.bid_notice_no, bookmark.bid_notice_ord || '000'),
        backendApi.getBidAValue(bookmark.bid_notice_no),
      ]);
      if (!bid) {
        toast.error('공고 정보를 찾을 수 없습니다.', { id: toastId });
        return;
      }
      setCalcBid(bid);
      setCalcAValue(aValue);
      setCalcOpen(true);
      toast.dismiss(toastId);
    } catch {
      toast.error('공고 정보를 불러오는데 실패했습니다.', { id: toastId });
    } finally {
      setCalcLoading(false);
    }
  };

  // ── 투찰완료 tab: filter + sort ──

  const now = useMemo(() => new Date(), [bookmarks]); // refresh on data change

  const statusMap = useMemo(() => {
    const m = new Map<string, OpengStatus>();
    for (const b of bookmarks) {
      m.set(b.bookmark_id, getOpengStatus(b, now));
    }
    return m;
  }, [bookmarks, now]);

  const filterCounts = useMemo(() => {
    const counts: Record<BidFilter, number> = { all: 0, today: 0, upcoming: 0, waiting: 0, completed: 0 };
    counts.all = bookmarks.length;
    for (const b of bookmarks) {
      const s = statusMap.get(b.bookmark_id)!;
      counts[s]++;
    }
    return counts;
  }, [bookmarks, statusMap]);

  const filteredAndSorted = useMemo(() => {
    let list = bookmarks;
    if (bidFilter !== 'all') {
      list = list.filter((b) => statusMap.get(b.bookmark_id) === bidFilter);
    }
    const sorted = [...list].sort((a, b) => {
      let va: string | number = '';
      let vb: string | number = '';
      if (sortField === 'openg_dt') {
        va = a.openg_dt || '';
        vb = b.openg_dt || '';
      } else if (sortField === 'bid_close_dt') {
        va = a.bid_close_dt || '';
        vb = b.bid_close_dt || '';
      } else if (sortField === 'rank') {
        va = a.rank ? parseInt(a.rank) : 9999;
        vb = b.rank ? parseInt(b.rank) : 9999;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [bookmarks, bidFilter, sortField, sortDir, statusMap]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-1 opacity-30 text-[10px]">↕</span>;
    return sortDir === 'asc'
      ? <ChevronUp className="h-3 w-3 ml-0.5 inline" />
      : <ChevronDown className="h-3 w-3 ml-0.5 inline" />;
  };

  // ── render ──

  return (
    <div className="min-h-screen bg-gray-50">
      <Header onLogout={() => navigate('/')} />

      <div className="mx-auto px-4 py-8 max-w-[1800px]">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <LayoutDashboard className="h-8 w-8 text-blue-600" />
            <div>
              <h2 className="text-3xl font-bold text-gray-900">대시보드</h2>
              <p className="text-sm text-gray-600 mt-1">
                관심공고와 투찰완료 공고를 관리하세요
              </p>
            </div>
          </div>
          <Button onClick={() => navigate('/')} variant="outline">
            검색 페이지로 돌아가기
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="bid_completed" className="gap-2">
              <CheckCircle className="h-4 w-4" />
              투찰완료
            </TabsTrigger>
            <TabsTrigger value="interested" className="gap-2">
              <Star className="h-4 w-4" />
              관심공고
            </TabsTrigger>
          </TabsList>

          <TabsContent value="bid_completed">
            {renderBidCompletedTable()}
          </TabsContent>

          <TabsContent value="interested">
            {renderInterestedTable()}
          </TabsContent>
        </Tabs>
      </div>

      {/* Edit Notes Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>메모 수정</DialogTitle>
            <DialogDescription>{selectedBookmark?.bid_notice_name}</DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Textarea
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
              placeholder="메모를 입력하세요..."
              rows={5}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>취소</Button>
            <Button onClick={handleSaveNotes}>저장</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bid Price Dialog */}
      <Dialog open={bidPriceDialogOpen} onOpenChange={setBidPriceDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>투찰완료로 변경</DialogTitle>
            <DialogDescription>{selectedBookmark?.bid_notice_name}</DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-3">
            <div className="flex items-center gap-2">
              <Input
                placeholder="투찰가를 입력하세요 (원)"
                value={bidPriceInput}
                onChange={(e) => setBidPriceInput(e.target.value)}
                type="number"
                className="flex-1"
              />
              <Button onClick={() => handleSaveBidPrice(true)}>저장</Button>
            </div>
            <Button variant="outline" className="w-full" onClick={() => handleSaveBidPrice(false)}>
              가격 없이 저장
            </Button>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setBidPriceDialogOpen(false)}>취소</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>삭제 확인</AlertDialogTitle>
            <AlertDialogDescription>
              정말로 삭제하시겠습니까?
              <span className="font-medium text-gray-900 mt-2 block">
                {selectedBookmark?.bid_notice_name}
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-600 hover:bg-red-700">
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Result Dialog */}
      <BidResultDialog
        bidNtceNo={resultBidNtceNo}
        bidNoticeName={resultBidName}
        isOpen={resultDialogOpen}
        onClose={() => setResultDialogOpen(false)}
      />

      {/* Bid Calculator Popup */}
      <BidCalculator
        bid={calcBid}
        aValueItem={calcAValue}
        isOpen={calcOpen}
        onClose={() => {
          setCalcOpen(false);
          loadBookmarks();
        }}
      />
    </div>
  );

  // ── handleSaveBidPrice (used by dialog) ──
  async function handleSaveBidPrice(withPrice: boolean) {
    if (!selectedBookmark) return;
    const update: { status: string; bid_price?: number } = { status: 'bid_completed' };
    if (withPrice) {
      const price = parseInt(bidPriceInput.replace(/,/g, ''), 10);
      if (!price || price <= 0) { toast.error('투찰가를 입력해주세요'); return; }
      update.bid_price = price;
    }
    try {
      await backendApi.updateBookmark(selectedBookmark.bookmark_id, update);
      toast.success('투찰완료로 변경되었습니다');
      setBidPriceDialogOpen(false);
      loadBookmarks();
    } catch {
      toast.error('변경에 실패했습니다');
    }
  }

  // ── 관심 탭 테이블 ──
  function renderInterestedTable() {
    if (loading) return <Spinner />;
    if (bookmarks.length === 0) return <EmptyState tab="interested" />;

    return (
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[110px] whitespace-nowrap">공고번호</TableHead>
              <TableHead className="max-w-[280px]">공고명</TableHead>
              <TableHead className="w-[80px] whitespace-nowrap">마감</TableHead>
              <TableHead className="w-[80px] whitespace-nowrap">개찰</TableHead>
              <TableHead className="w-[60px] text-center whitespace-nowrap">상태</TableHead>
              <TableHead className="w-[180px]">메모</TableHead>
              <TableHead className="w-[120px] text-center whitespace-nowrap">작업</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bookmarks.map((b) => {
              const status = statusMap.get(b.bookmark_id) || 'upcoming';
              const cfg = STATUS_CFG[status];
              return (
                <TableRow key={b.bookmark_id}>
                  <TableCell className="font-mono text-xs">{b.bid_notice_no}</TableCell>
                  <TableCell className="max-w-[280px]">
                    <button
                      type="button"
                      className="text-left font-medium text-blue-600 hover:text-blue-800 hover:underline cursor-pointer truncate block max-w-full"
                      onClick={() => handleOpenCalculator(b)}
                      disabled={calcLoading}
                      title={b.bid_notice_name}
                    >
                      {b.bid_notice_name}
                    </button>
                  </TableCell>
                  <TableCell className="text-xs whitespace-nowrap text-gray-600">{formatDt(b.bid_close_dt)}</TableCell>
                  <TableCell className="text-xs whitespace-nowrap text-gray-600">{formatDt(b.openg_dt)}</TableCell>
                  <TableCell className="text-center">
                    <span className={`inline-block px-1.5 py-0.5 text-[10px] font-medium rounded whitespace-nowrap ${cfg.bg} ${cfg.text}`}>
                      {cfg.label}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-gray-600">
                    {b.notes ? <span className="line-clamp-2">{b.notes}</span> : <span className="text-gray-400 italic">-</span>}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-center gap-1">
                      <Button variant="ghost" size="sm" title="투찰완료로 변경" onClick={() => handleChangeToBidCompleted(b)}>
                        <ArrowRightLeft className="h-4 w-4 text-green-600" />
                      </Button>
                      <Button variant="ghost" size="sm" title="메모 수정" onClick={() => handleEditClick(b)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" title="삭제" onClick={() => handleDeleteClick(b)}>
                        <Trash2 className="h-4 w-4 text-red-600" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    );
  }

  // ── 투찰완료 탭 테이블 ──
  function renderBidCompletedTable() {
    if (loading) return <Spinner />;
    if (bookmarks.length === 0) return <EmptyState tab="bid_completed" />;

    const filters: { key: BidFilter; label: string; color: string }[] = [
      { key: 'all',       label: '전체',     color: 'bg-gray-100 text-gray-700 hover:bg-gray-200' },
      { key: 'today',     label: '오늘 개찰', color: 'bg-orange-50 text-orange-700 hover:bg-orange-100' },
      { key: 'upcoming',  label: '개찰 전',   color: 'bg-blue-50 text-blue-700 hover:bg-blue-100' },

      { key: 'completed', label: '개찰완료',  color: 'bg-green-50 text-green-700 hover:bg-green-100' },
    ];

    return (
      <div className="space-y-3">
        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap">
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                bidFilter === f.key
                  ? `${f.color} ring-2 ring-offset-1 ring-gray-300`
                  : `${f.color} opacity-60`
              }`}
              onClick={() => setBidFilter(f.key)}
            >
              {f.label}
              <span className="ml-1 font-bold">{filterCounts[f.key]}</span>
            </button>
          ))}
        </div>

        <div className="bg-white rounded-lg shadow overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[110px] whitespace-nowrap">공고번호</TableHead>
                <TableHead className="max-w-[200px] whitespace-nowrap">공고명</TableHead>
                <TableHead
                  className="w-[80px] whitespace-nowrap cursor-pointer select-none hover:bg-muted/50"
                  onClick={() => handleSort('bid_close_dt')}
                >
                  마감<SortIcon field="bid_close_dt" />
                </TableHead>
                <TableHead
                  className="w-[80px] whitespace-nowrap cursor-pointer select-none hover:bg-muted/50"
                  onClick={() => handleSort('openg_dt')}
                >
                  개찰<SortIcon field="openg_dt" />
                </TableHead>
                <TableHead className="w-[60px] text-center whitespace-nowrap">상태</TableHead>
                <TableHead className="w-[130px] text-right whitespace-nowrap">투찰금액</TableHead>
                <TableHead className="w-[60px] text-right whitespace-nowrap">투찰률</TableHead>
                <TableHead
                  className="w-[75px] text-center whitespace-nowrap cursor-pointer select-none hover:bg-muted/50"
                  onClick={() => handleSort('rank')}
                >
                  순위/참여<SortIcon field="rank" />
                </TableHead>
                <TableHead className="w-[80px] text-right whitespace-nowrap">낙찰금액</TableHead>
                <TableHead className="w-[60px] text-right whitespace-nowrap">낙찰률</TableHead>
                <TableHead className="w-[90px] text-center whitespace-nowrap">작업</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAndSorted.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={11} className="text-center py-8 text-gray-500">
                    해당하는 공고가 없습니다
                  </TableCell>
                </TableRow>
              ) : (
                filteredAndSorted.map((b) => {
                  const status = statusMap.get(b.bookmark_id) || 'upcoming';
                  const cfg = STATUS_CFG[status];
                  const isHighlight = status === 'today';
                  const rankNum = b.rank ? parseInt(b.rank) : null;
                  const isNegativeRank = rankNum !== null && rankNum < 0;

                  // 투찰금액 - 낙찰금액 차이 계산
                  const myAmt = b.actual_bid_price ? parseFloat(b.actual_bid_price) : null;
                  const winAmt = b.winning_bid_price ? parseFloat(b.winning_bid_price) : null;
                  const diff = myAmt !== null && winAmt !== null ? myAmt - winAmt : null;

                  return (
                    <TableRow key={b.bookmark_id} className={isHighlight ? 'bg-orange-50/50' : ''}>
                      <TableCell className="font-mono text-xs">{b.bid_notice_no}</TableCell>
                      <TableCell className="max-w-[200px]">
                        <button
                          type="button"
                          className="text-left font-medium text-blue-600 hover:text-blue-800 hover:underline cursor-pointer truncate block max-w-full"
                          onClick={() => handleViewResults(b)}
                          title={b.bid_notice_name}
                        >
                          {b.bid_notice_name}
                        </button>
                      </TableCell>
                      <TableCell className="text-xs whitespace-nowrap text-gray-600">
                        {formatDt(b.bid_close_dt)}
                      </TableCell>
                      <TableCell className={`text-xs whitespace-nowrap ${isHighlight ? 'font-semibold text-orange-700' : 'text-gray-600'}`}>
                        {formatDt(b.openg_dt)}
                      </TableCell>
                      <TableCell className="text-center">
                        <span className={`inline-block px-1.5 py-0.5 text-[10px] font-medium rounded whitespace-nowrap ${cfg.bg} ${cfg.text}`}>
                          {cfg.label}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs whitespace-nowrap">
                        {myAmt !== null ? (
                          <div>
                            <span title={myAmt.toLocaleString() + '원'}>
                              {formatAmt(b.actual_bid_price)}
                            </span>
                            {diff !== null && diff !== 0 && (
                              <span
                                className={`ml-1 text-[10px] ${diff > 0 ? 'text-red-500' : 'text-blue-500'}`}
                                title={`낙찰금액 대비 ${diff > 0 ? '+' : ''}${diff.toLocaleString()}원`}
                              >
                                ({diff > 0 ? '+' : '-'}{formatAmt(String(Math.abs(diff)))})
                              </span>
                            )}
                          </div>
                        ) : b.bid_price ? (
                          <span className="text-gray-500" title={b.bid_price.toLocaleString() + '원 (직접입력)'}>
                            {formatAmt(String(b.bid_price))}
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-xs whitespace-nowrap">
                        {b.bid_rate ? `${b.bid_rate}%` : '-'}
                      </TableCell>
                      <TableCell className="text-center text-xs font-semibold whitespace-nowrap">
                        {rankNum !== null && b.total_bidders ? (
                          <span className={isNegativeRank ? 'text-red-500' : ''}>
                            {rankNum}/{b.total_bidders}등
                          </span>
                        ) : rankNum !== null ? (
                          <span className={isNegativeRank ? 'text-red-500' : ''}>
                            {rankNum}등
                          </span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs whitespace-nowrap">
                        {b.winning_bid_price ? (
                          <span title={parseFloat(b.winning_bid_price).toLocaleString() + '원'}>
                            {formatAmt(b.winning_bid_price)}
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-xs whitespace-nowrap">
                        {b.winning_bid_rate ? `${b.winning_bid_rate}%` : '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-center gap-0.5">
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" title="결과보기" onClick={() => handleViewResults(b)}>
                            <Trophy className="h-3.5 w-3.5 text-yellow-600" />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" title="메모 수정" onClick={() => handleEditClick(b)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" title="삭제" onClick={() => handleDeleteClick(b)}>
                            <Trash2 className="h-3.5 w-3.5 text-red-600" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    );
  }

  function Spinner() {
    return (
      <div className="text-center py-12">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
      </div>
    );
  }

  function EmptyState({ tab }: { tab: string }) {
    return (
      <div className="bg-white rounded-lg shadow p-12 text-center">
        {tab === 'interested' ? (
          <Star className="h-16 w-16 text-gray-300 mx-auto mb-4" />
        ) : (
          <CheckCircle className="h-16 w-16 text-gray-300 mx-auto mb-4" />
        )}
        <h3 className="text-xl font-semibold text-gray-900 mb-2">
          {tab === 'interested' ? '관심공고가 없습니다' : '투찰완료 공고가 없습니다'}
        </h3>
        <p className="text-gray-600 mb-6">검색 결과에서 공고를 저장해보세요</p>
        <Button onClick={() => navigate('/')}>입찰 공고 검색하기</Button>
      </div>
    );
  }
}
