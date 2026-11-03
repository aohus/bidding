const ALLOWED_PROTOCOLS: ReadonlySet<string> = new Set(['http:', 'https:']);
// 브라우저 밖(테스트 등)에서 상대 경로를 해석할 기준 URL
const FALLBACK_BASE_URL = 'http://localhost/';

const currentBaseUrl = (): string =>
  typeof window !== 'undefined' && window.location?.href ? window.location.href : FALLBACK_BASE_URL;

/**
 * http:/https: 스킴만 허용한다. 상대 경로는 현재 페이지 기준으로 해석한다.
 * javascript:, data: 등 다른 스킴, URL 내 자격증명(user:pass@), 파싱 불가 문자열은 거부한다.
 */
export function isSafeHttpUrl(url: string): boolean {
  if (typeof url !== 'string' || !url.trim()) return false;
  try {
    const parsed = new URL(url, currentBaseUrl());
    return ALLOWED_PROTOCOLS.has(parsed.protocol) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export function downloadDocument(url: string, filename: string): void {
  if (!isSafeHttpUrl(url)) return;

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
