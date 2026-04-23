import { BookmarkWithStatus } from '@/types/bid';

/** "202502101500" → Date */
export function parseDt(dt?: string): Date | null {
  if (!dt || dt.length < 12) return null;
  const y = +dt.slice(0, 4), m = +dt.slice(4, 6) - 1, d = +dt.slice(6, 8);
  const h = +dt.slice(8, 10), mi = +dt.slice(10, 12);
  return new Date(y, m, d, h, mi);
}

/** "202502101500" → "02/10 15:00" */
export function formatDt(dt?: string): string {
  if (!dt || dt.length < 12) return '-';
  return `${dt.slice(4, 6)}/${dt.slice(6, 8)} ${dt.slice(8, 10)}:${dt.slice(10, 12)}`;
}

export function formatAmt(amt?: string): string {
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

export type OpengStatus = 'today' | 'upcoming' | 'waiting' | 'completed';

export function getOpengStatus(b: BookmarkWithStatus, now: Date): OpengStatus {
  const openg = parseDt(b.openg_dt);
  if (!openg) return b.openg_completed ? 'completed' : 'upcoming';

  const isToday =
    openg.getFullYear() === now.getFullYear() &&
    openg.getMonth() === now.getMonth() &&
    openg.getDate() === now.getDate();

  if (b.openg_completed) return 'completed';
  if (isToday) return 'today';
  if (openg > now) return 'upcoming';
  return 'waiting';
}

export const STATUS_CFG: Record<OpengStatus, { label: string; bg: string; text: string }> = {
  today:     { label: '오늘 개찰', bg: 'bg-orange-100', text: 'text-orange-700' },
  upcoming:  { label: '개찰 전',   bg: 'bg-blue-100',   text: 'text-blue-700' },
  waiting:   { label: '결과 대기', bg: 'bg-yellow-100', text: 'text-yellow-700' },
  completed: { label: '개찰완료',  bg: 'bg-green-100',  text: 'text-green-700' },
};
