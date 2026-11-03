import { describe, it, expect, vi, afterEach } from 'vitest';
import { isSafeHttpUrl, downloadDocument } from '../download';

describe('isSafeHttpUrl', () => {
  it.each([
    ['https://www.g2b.go.kr/file/1'],
    ['http://www.g2b.go.kr/file/1'],
    ['HTTPS://WWW.G2B.GO.KR/file'],
    ['/server/bids/files/1'],
  ])('http/https URL은 허용한다: %s', (url) => {
    expect(isSafeHttpUrl(url)).toBe(true);
  });

  it.each([
    ['javascript:alert(1)'],
    ['  JaVaScRiPt:alert(1)'],
    ['java\tscript:alert(1)'],
    ['data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=='],
    ['vbscript:msgbox(1)'],
    ['file:///etc/passwd'],
    ['ftp://example.com/a.pdf'],
    ['https://user:pass@evil.example.com/a.pdf'],
    ['https://user@evil.example.com/a.pdf'],
    ['http://[::1'],
    [''],
    ['   '],
  ])('안전하지 않거나 파싱 불가한 URL은 거부한다: %s', (url) => {
    expect(isSafeHttpUrl(url)).toBe(false);
  });

  it('문자열이 아닌 값은 거부한다', () => {
    expect(isSafeHttpUrl(undefined as unknown as string)).toBe(false);
    expect(isSafeHttpUrl(null as unknown as string)).toBe(false);
  });
});

describe('downloadDocument', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const stubDocument = () => {
    const link = { href: '', download: '', target: '', rel: '', click: vi.fn() };
    const doc = {
      createElement: vi.fn(() => link),
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    };
    vi.stubGlobal('document', doc);
    return { doc, link };
  };

  it('안전한 URL이면 링크를 만들어 클릭한다', () => {
    // Arrange
    const { doc, link } = stubDocument();

    // Act
    downloadDocument('https://www.g2b.go.kr/file/1', '공고문.pdf');

    // Assert
    expect(doc.createElement).toHaveBeenCalledWith('a');
    expect(link.href).toBe('https://www.g2b.go.kr/file/1');
    expect(link.download).toBe('공고문.pdf');
    expect(link.rel).toBe('noopener noreferrer');
    expect(link.click).toHaveBeenCalledTimes(1);
  });

  it.each([['javascript:alert(1)'], ['data:text/html,<b>x</b>'], ['https://u:p@evil.example.com'], ['']])(
    '안전하지 않은 URL이면 아무 것도 하지 않는다: %s',
    (url) => {
      const { doc, link } = stubDocument();

      downloadDocument(url, 'x.pdf');

      expect(doc.createElement).not.toHaveBeenCalled();
      expect(link.click).not.toHaveBeenCalled();
    },
  );
});
