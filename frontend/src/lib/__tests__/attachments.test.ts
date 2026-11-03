import { describe, it, expect } from 'vitest';
import { groupAttachments, legacyAttachmentsFromBid, ETC_GROUP_LABEL } from '../attachments';
import { BidAttachment, BidItem } from '@/types/bid';

const makeAttachment = (overrides: Partial<BidAttachment> = {}): BidAttachment => ({
  source: 'ntce',
  docDivNm: '공고서',
  fileNm: '공고문.pdf',
  fileUrl: 'https://www.g2b.go.kr/file/1',
  sno: 1,
  ...overrides,
});

const makeBid = (overrides: Partial<BidItem> = {}): BidItem => ({
  bidNtceNo: 'R26BK00000001',
  bidNtceOrd: '000',
  bidNtceNm: '테스트 공사',
  ntceInsttNm: '조달청',
  dminsttNm: '',
  bidMethdNm: '',
  cntrctCnclsMthdNm: '',
  bidBeginDt: '',
  bidClseDt: '',
  opengDt: '',
  bdgtAmt: '',
  presmptPrce: '',
  prearngPrceDcsnMthdNm: '',
  sucsfbidLwltRate: '',
  sucsfbidMthdNm: '',
  rgstDt: '',
  ...overrides,
});

describe('groupAttachments', () => {
  it('빈 배열이면 빈 그룹 목록을 반환한다', () => {
    expect(groupAttachments([])).toEqual([]);
  });

  it('docDivNm 기준으로 그룹핑하고 공고서 그룹을 맨 앞에 둔다', () => {
    // Arrange
    const items = [
      makeAttachment({ docDivNm: '내역서', fileNm: 'a.xlsx', fileUrl: 'u1', sno: 1 }),
      makeAttachment({ docDivNm: '공고서', fileNm: 'b.pdf', fileUrl: 'u2', sno: 2 }),
      makeAttachment({ docDivNm: '내역서', fileNm: 'c.xlsx', fileUrl: 'u3', sno: 3 }),
    ];

    // Act
    const groups = groupAttachments(items);

    // Assert
    expect(groups.map((g) => g.label)).toEqual(['공고서', '내역서']);
    expect(groups[1].items.map((i) => i.fileNm)).toEqual(['a.xlsx', 'c.xlsx']);
  });

  it('docDivNm이 null/공백이면 기타 그룹으로 묶고 기타는 맨 뒤에 둔다', () => {
    const items = [
      makeAttachment({ docDivNm: null, fileNm: 'x', fileUrl: 'u1' }),
      makeAttachment({ docDivNm: '  ', fileNm: 'y', fileUrl: 'u2' }),
      makeAttachment({ docDivNm: '시방서', fileNm: 'z', fileUrl: 'u3' }),
    ];

    const groups = groupAttachments(items);

    expect(groups.map((g) => g.label)).toEqual(['시방서', ETC_GROUP_LABEL]);
    expect(groups[1].items.map((i) => i.fileNm)).toEqual(['x', 'y']);
  });

  it('e발주 첨부는 "e발주 " 접두 라벨로 별도 그룹을 만들고 일반 첨부 뒤에 둔다', () => {
    const items = [
      makeAttachment({ source: 'eorder', docDivNm: '제안요청서', fileNm: 'rfp.hwp', fileUrl: 'e1' }),
      makeAttachment({ source: 'ntce', docDivNm: '제안요청서', fileNm: 'n.pdf', fileUrl: 'n1' }),
      makeAttachment({ source: 'eorder', docDivNm: null, fileNm: 'etc.zip', fileUrl: 'e2' }),
    ];

    const groups = groupAttachments(items);

    expect(groups.map((g) => g.label)).toEqual(['제안요청서', 'e발주 제안요청서', 'e발주 기타']);
  });

  it('그룹 내부는 sno 오름차순, sno가 없으면 원래 순서를 유지하며 뒤에 둔다', () => {
    const items = [
      makeAttachment({ docDivNm: '내역서', fileNm: 'n1', fileUrl: 'u1', sno: null }),
      makeAttachment({ docDivNm: '내역서', fileNm: 's3', fileUrl: 'u2', sno: 3 }),
      makeAttachment({ docDivNm: '내역서', fileNm: 'n2', fileUrl: 'u3', sno: null }),
      makeAttachment({ docDivNm: '내역서', fileNm: 's1', fileUrl: 'u4', sno: 1 }),
    ];

    const groups = groupAttachments(items);

    expect(groups[0].items.map((i) => i.fileNm)).toEqual(['s1', 's3', 'n1', 'n2']);
  });

  it('fileUrl이 비어있는 항목은 제외한다', () => {
    const items = [
      makeAttachment({ fileUrl: '' }),
      makeAttachment({ fileUrl: 'https://ok', fileNm: 'ok.pdf' }),
    ];

    const groups = groupAttachments(items);

    expect(groups).toHaveLength(1);
    expect(groups[0].items.map((i) => i.fileNm)).toEqual(['ok.pdf']);
  });

  it('http/https가 아니거나 자격증명이 포함된 URL은 제외한다', () => {
    // Arrange
    const items = [
      makeAttachment({ fileNm: 'js', fileUrl: 'javascript:alert(1)' }),
      makeAttachment({ fileNm: 'data', fileUrl: 'data:text/html,<script>alert(1)</script>' }),
      makeAttachment({ fileNm: 'cred', fileUrl: 'https://user:pass@evil.example.com/a.pdf' }),
      makeAttachment({ fileNm: 'junk', fileUrl: 'http://[::1' }),
      makeAttachment({ fileNm: 'http', fileUrl: 'http://www.g2b.go.kr/a.pdf', sno: 2 }),
      makeAttachment({ fileNm: 'https', fileUrl: 'https://www.g2b.go.kr/b.pdf', sno: 3 }),
    ];

    // Act
    const groups = groupAttachments(items);

    // Assert
    expect(groups.flatMap((g) => g.items.map((i) => i.fileNm))).toEqual(['http', 'https']);
  });

  it('입력 배열을 변경하지 않는다', () => {
    const items = [
      makeAttachment({ sno: 2, fileUrl: 'u2' }),
      makeAttachment({ sno: 1, fileUrl: 'u1' }),
    ];
    const snapshot = JSON.parse(JSON.stringify(items));

    groupAttachments(items);

    expect(items).toEqual(snapshot);
  });
});

describe('legacyAttachmentsFromBid', () => {
  it('URL이 없는 공고는 빈 배열을 반환한다', () => {
    expect(legacyAttachmentsFromBid(makeBid())).toEqual([]);
  });

  it('공고규격서/현장설명서/표준공고서 URL을 legacy 첨부로 변환한다', () => {
    // Arrange
    const bid = makeBid({
      ntceSpecDocUrl1: 'https://spec1',
      ntceSpecFileNm1: '공고문.hwp',
      ntceSpecDocUrl3: 'https://spec3',
      sptDscrptDocUrl2: 'https://spt2',
      sptDscrptFileNm2: '현설.pdf',
      stdNtceDocUrl: 'https://std',
    });

    // Act
    const result = legacyAttachmentsFromBid(bid);

    // Assert
    expect(result).toEqual([
      { source: 'legacy', docDivNm: '공고규격서', fileNm: '공고문.hwp', fileUrl: 'https://spec1', sno: 1 },
      { source: 'legacy', docDivNm: '공고규격서', fileNm: '공고규격서 3', fileUrl: 'https://spec3', sno: 3 },
      { source: 'legacy', docDivNm: '현장설명서', fileNm: '현설.pdf', fileUrl: 'https://spt2', sno: 2 },
      { source: 'legacy', docDivNm: '표준공고서', fileNm: '표준공고서', fileUrl: 'https://std', sno: null },
    ]);
  });

  it('표준공고서 파일명이 있으면 사용하고 공백 URL은 무시한다', () => {
    const bid = makeBid({
      ntceSpecDocUrl2: '   ',
      stdNtceDocUrl: 'https://std',
      stdNtceDocFileNm: '표준공고.pdf',
    });

    const result = legacyAttachmentsFromBid(bid);

    expect(result).toHaveLength(1);
    expect(result[0].fileNm).toBe('표준공고.pdf');
  });

  it('안전하지 않은 스킴(javascript:, data:)이나 자격증명 URL은 제외한다', () => {
    const bid = makeBid({
      ntceSpecDocUrl1: 'javascript:alert(1)',
      ntceSpecDocUrl2: 'https://spec2',
      sptDscrptDocUrl1: 'data:text/html,<b>x</b>',
      sptDscrptDocUrl2: 'https://user:pass@evil.example.com/a.pdf',
      stdNtceDocUrl: 'http://std',
    });

    const result = legacyAttachmentsFromBid(bid);

    expect(result.map((i) => i.fileUrl)).toEqual(['https://spec2', 'http://std']);
  });

  it('groupAttachments와 함께 쓰면 문서 종류별로 묶인다', () => {
    const bid = makeBid({
      sptDscrptDocUrl1: 'https://spt1',
      ntceSpecDocUrl1: 'https://spec1',
    });

    const groups = groupAttachments(legacyAttachmentsFromBid(bid));

    expect(groups.map((g) => g.label)).toEqual(['공고규격서', '현장설명서']);
  });
});
