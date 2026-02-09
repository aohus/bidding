import { Button } from '@/components/ui/button';
import { AuthService } from '@/lib/auth';
import { LogOut, User, BookmarkIcon, Search } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface HeaderProps {
  onLogout: () => void;
}

export default function Header({ onLogout }: HeaderProps) {
  const [username, setUsername] = useState<string>('');
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    loadUserInfo();
  }, []);

  const loadUserInfo = async () => {
    try {
      const user = await AuthService.getCurrentUser();
      setUsername(user.username);
    } catch (error) {
      console.error('Failed to load user info');
    }
  };

  const handleLogout = () => {
    AuthService.logout();
    onLogout();
  };

  const isBookmarksPage = location.pathname === '/bookmarks';

  return (
    <header className="border-b bg-white shadow-sm">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">입찰 정보 시스템</h1>
          <p className="text-sm text-gray-600">건설 입찰 공고 검색 및 관리</p>
        </div>
        <div className="flex items-center gap-4">
          {isBookmarksPage ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/')}
            >
              <Search className="mr-2 h-4 w-4" />
              검색
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/bookmarks')}
            >
              <BookmarkIcon className="mr-2 h-4 w-4" />
              북마크
            </Button>
          )}
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <User className="h-4 w-4" />
            <span>{username}</span>
          </div>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            로그아웃
          </Button>
        </div>
      </div>
    </header>
  );
}