import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { backendApi } from '@/lib/backendApi';
import { toast } from 'sonner';
import { Trash2 } from 'lucide-react';

interface SavedSearch {
  search_id: string;
  search_name: string;
  filters: any;
  created_at: string;
}

interface SavedSearchListProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (filters: any) => void;
}

export function SavedSearchList({ isOpen, onClose, onSelect }: SavedSearchListProps) {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadSearches();
    }
  }, [isOpen]);

  const loadSearches = async () => {
    setLoading(true);
    try {
      const data = await backendApi.getSavedSearches();
      setSearches(data);
    } catch (error) {
      toast.error('저장된 검색 조건을 불러오는데 실패했습니다');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('삭제하시겠습니까?')) return;
    try {
      await backendApi.deleteSavedSearch(id);
      setSearches(searches.filter(s => s.search_id !== id));
      toast.success('삭제되었습니다');
    } catch (error) {
      toast.error('삭제 실패');
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>저장된 검색 조건</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 mt-2 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <p className="text-center py-4 text-gray-500">로딩 중...</p>
          ) : searches.length === 0 ? (
            <p className="text-center py-4 text-gray-500">저장된 조건이 없습니다</p>
          ) : (
            searches.map((item) => (
              <div
                key={item.search_id}
                className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50 transition-colors"
              >
                <button
                  className="flex-1 text-left font-medium"
                  onClick={() => {
                    onSelect(item.filters);
                    onClose();
                  }}
                >
                  {item.search_name}
                  <span className="block text-xs text-gray-400 font-normal mt-1">
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-gray-400 hover:text-red-500"
                  onClick={() => handleDelete(item.search_id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
