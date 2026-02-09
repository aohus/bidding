import { useState, useEffect } from 'react';
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
import { Pencil, Trash2, BookmarkIcon } from 'lucide-react';
import { toast } from 'sonner';
import Header from '@/components/Header';
import { useNavigate } from 'react-router-dom';

interface Bookmark {
  bookmark_id: string;
  user_id: string;
  bid_notice_no: string;
  bid_notice_name: string;
  notes?: string;
  created_at: string;
}

export default function Bookmarks() {
  const navigate = useNavigate();
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(true);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedBookmark, setSelectedBookmark] = useState<Bookmark | null>(null);
  const [editNotes, setEditNotes] = useState('');

  useEffect(() => {
    loadBookmarks();
  }, []);

  const loadBookmarks = async () => {
    try {
      setLoading(true);
      const data = await backendApi.getBookmarks();
      setBookmarks(data);
    } catch (error) {
      toast.error('북마크를 불러오는데 실패했습니다');
      console.error('Failed to load bookmarks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEditClick = (bookmark: Bookmark) => {
    setSelectedBookmark(bookmark);
    setEditNotes(bookmark.notes || '');
    setEditDialogOpen(true);
  };

  const handleSaveNotes = async () => {
    if (!selectedBookmark) return;

    try {
      // Delete old bookmark and create new one with updated notes
      await backendApi.deleteBookmark(selectedBookmark.bookmark_id);
      await backendApi.createBookmark(
        selectedBookmark.bid_notice_no,
        selectedBookmark.bid_notice_name,
        editNotes
      );
      
      toast.success('메모가 수정되었습니다');
      setEditDialogOpen(false);
      loadBookmarks();
    } catch (error) {
      toast.error('메모 수정에 실패했습니다');
      console.error('Failed to update notes:', error);
    }
  };

  const handleDeleteClick = (bookmark: Bookmark) => {
    setSelectedBookmark(bookmark);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedBookmark) return;

    try {
      await backendApi.deleteBookmark(selectedBookmark.bookmark_id);
      toast.success('북마크가 삭제되었습니다');
      setDeleteDialogOpen(false);
      loadBookmarks();
    } catch (error) {
      toast.error('북마크 삭제에 실패했습니다');
      console.error('Failed to delete bookmark:', error);
    }
  };

  const handleLogout = () => {
    navigate('/');
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header onLogout={handleLogout} />
      
      <div className="container mx-auto px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BookmarkIcon className="h-8 w-8 text-blue-600" />
            <div>
              <h2 className="text-3xl font-bold text-gray-900">내 북마크</h2>
              <p className="text-sm text-gray-600 mt-1">
                저장한 입찰 공고 목록을 관리하세요
              </p>
            </div>
          </div>
          <Button onClick={() => navigate('/')} variant="outline">
            검색 페이지로 돌아가기
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
            <p className="mt-4 text-gray-600">북마크를 불러오는 중...</p>
          </div>
        ) : bookmarks.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <BookmarkIcon className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              저장된 북마크가 없습니다
            </h3>
            <p className="text-gray-600 mb-6">
              검색 결과에서 관심있는 입찰 공고를 북마크로 저장해보세요
            </p>
            <Button onClick={() => navigate('/')}>
              입찰 공고 검색하기
            </Button>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[150px]">공고번호</TableHead>
                  <TableHead>공고명</TableHead>
                  <TableHead className="w-[250px]">메모</TableHead>
                  <TableHead className="w-[180px]">저장일시</TableHead>
                  <TableHead className="w-[120px] text-center">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bookmarks.map((bookmark) => (
                  <TableRow key={bookmark.bookmark_id}>
                    <TableCell className="font-mono text-sm">
                      {bookmark.bid_notice_no}
                    </TableCell>
                    <TableCell className="font-medium">
                      {bookmark.bid_notice_name}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {bookmark.notes ? (
                        <span className="line-clamp-2">{bookmark.notes}</span>
                      ) : (
                        <span className="text-gray-400 italic">메모 없음</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {formatDate(bookmark.created_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditClick(bookmark)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(bookmark)}
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Edit Notes Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>메모 수정</DialogTitle>
            <DialogDescription>
              {selectedBookmark?.bid_notice_name}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              메모
            </label>
            <Textarea
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
              placeholder="이 입찰 공고에 대한 메모를 입력하세요..."
              rows={5}
              className="w-full"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditDialogOpen(false)}
            >
              취소
            </Button>
            <Button onClick={handleSaveNotes}>
              저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>북마크 삭제</AlertDialogTitle>
            <AlertDialogDescription>
              정말로 이 북마크를 삭제하시겠습니까?
              <br />
              <span className="font-medium text-gray-900 mt-2 block">
                {selectedBookmark?.bid_notice_name}
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-red-600 hover:bg-red-700"
            >
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}