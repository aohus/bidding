import { useState, useEffect, useCallback } from 'react';
import { AuthService } from '@/lib/auth';

interface SessionTimer {
  remainingMs: number;
  remainingText: string;
  isExpired: boolean;
  isUrgent: boolean;
}

export function useSessionTimer(onExpired: () => void): SessionTimer {
  const [remainingMs, setRemainingMs] = useState<number>(() => {
    const expiry = AuthService.getTokenExpiry();
    return expiry ? Math.max(0, expiry - Date.now()) : 0;
  });

  const handleExpired = useCallback(() => {
    AuthService.triggerExpired();
    onExpired();
  }, [onExpired]);

  useEffect(() => {
    const timer = setInterval(() => {
      const expiry = AuthService.getTokenExpiry();
      if (!expiry) {
        setRemainingMs(0);
        return;
      }
      const remaining = Math.max(0, expiry - Date.now());
      setRemainingMs(remaining);

      if (remaining <= 0) {
        clearInterval(timer);
        handleExpired();
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [handleExpired]);

  const totalSeconds = Math.floor(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const remainingText = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  return {
    remainingMs,
    remainingText,
    isExpired: remainingMs <= 0,
    isUrgent: remainingMs > 0 && remainingMs <= 5 * 60 * 1000,
  };
}
