import { Button } from '@/components/ui/button';
import { AuthService } from '@/lib/auth';
import { LogOut, User, LayoutDashboard, Search, Settings, Clock } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSessionTimer } from '@/hooks/useSessionTimer';

interface HeaderProps {
  onLogout: () => void;
}

export default function Header({ onLogout }: HeaderProps) {
  const [username, setUsername] = useState<string>('');
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    AuthService.logout();
    onLogout();
  };

  const { remainingText, isUrgent } = useSessionTimer(handleLogout);

  useEffect(() => {
    loadUserInfo();
  }, []);

  const loadUserInfo = async () => {
    try {
      const user = await AuthService.getCurrentUser();
      setUsername(user.username);
    } catch {
      handleLogout();
    }
  };

  const isDashboardPage = location.pathname === '/dashboard';
  const isSettingsPage = location.pathname === '/settings';

  return (
    <header className="border-b bg-white shadow-sm">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">입찰 정보 시스템</h1>
          <p className="text-sm text-gray-600">건설 입찰 공고 검색 및 관리</p>
        </div>
        <div className="flex items-center gap-4">
          {isDashboardPage || isSettingsPage ? (
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
              onClick={() => navigate('/dashboard')}
            >
              <LayoutDashboard className="mr-2 h-4 w-4" />
              대시보드
            </Button>
          )}
          <Button
            variant={isSettingsPage ? 'default' : 'outline'}
            size="sm"
            onClick={() => navigate('/settings')}
          >
            <Settings className="mr-2 h-4 w-4" />
            정보수정
          </Button>
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <User className="h-4 w-4" />
            <span>{username}</span>
          </div>
          <div
            className={`flex items-center gap-1 text-sm font-mono px-2 py-1 rounded ${
              isUrgent
                ? 'bg-red-100 text-red-700'
                : 'bg-gray-100 text-gray-600'
            }`}
            title="세션 남은 시간"
          >
            <Clock className="h-3.5 w-3.5" />
            <span>{remainingText}</span>
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