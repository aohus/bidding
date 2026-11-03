import { BidAttachment, BidItem } from '@/types/bid';
import { isSafeHttpUrl } from '@/lib/download';

export const ETC_GROUP_LABEL = '기타';
export const EORDER_LABEL_PREFIX = 'e발주 ';
const PRIMARY_GROUP_LABEL = '공고서';

const NTCE_SPEC_DOC_COUNT = 5;
const SPT_DSCRPT_DOC_COUNT = 3;

export interface AttachmentGroup {
  label: string;
  items: BidAttachment[];
}

const toGroupLabel = (item: BidAttachment): string => {
  const base = item.docDivNm?.trim() || ETC_GROUP_LABEL;
  return item.source === 'eorder' ? `${EORDER_LABEL_PREFIX}${base}` : base;
};

/**
 * 그룹 정렬 우선순위 (작을수록 앞):
 * 0 공고서 → 1 일반 문서구분(첫 등장 순) → 2 일반 기타 → 3 e발주 문서구분 → 4 e발주 기타
 */
const groupRank = (label: string): number => {
  if (label === PRIMARY_GROUP_LABEL) return 0;
  const isEorder = label.startsWith(EORDER_LABEL_PREFIX);
  const isEtc = label === ETC_GROUP_LABEL || label === `${EORDER_LABEL_PREFIX}${ETC_GROUP_LABEL}`;
  return (isEorder ? 3 : 1) + (isEtc ? 1 : 0);
};

// sno 오름차순, sno 없는 항목은 뒤로 (Array.prototype.sort는 stable)
const compareBySno = (a: BidAttachment, b: BidAttachment): number => {
  if (a.sno == null && b.sno == null) return 0;
  if (a.sno == null) return 1;
  if (b.sno == null) return -1;
  return a.sno - b.sno;
};

/** 첨부파일을 문서구분명별로 묶는다. http(s)가 아닌 URL은 제외하며 입력 배열은 변경하지 않는다. */
export function groupAttachments(items: readonly BidAttachment[]): AttachmentGroup[] {
  const buckets = new Map<string, BidAttachment[]>();
  for (const item of items) {
    if (!item.fileUrl?.trim() || !isSafeHttpUrl(item.fileUrl)) continue;
    const label = toGroupLabel(item);
    buckets.set(label, [...(buckets.get(label) ?? []), item]);
  }

  return [...buckets.entries()]
    .map(([label, groupItems], order) => ({ label, items: [...groupItems].sort(compareBySno), order }))
    .sort((a, b) => groupRank(a.label) - groupRank(b.label) || a.order - b.order)
    .map(({ label, items: groupItems }) => ({ label, items: groupItems }));
}

const legacyItem = (
  url: string | undefined,
  fileNm: string | undefined,
  docDivNm: string,
  fallbackName: string,
  sno: number | null,
): BidAttachment | null => {
  const fileUrl = url?.trim();
  if (!fileUrl || !isSafeHttpUrl(fileUrl)) return null;
  return { source: 'legacy', docDivNm, fileNm: fileNm?.trim() || fallbackName, fileUrl, sno };
};

const range = (count: number): number[] => Array.from({ length: count }, (_, i) => i + 1);

/**
 * 공고 원문에 포함된 문서 URL 필드(ntceSpecDocUrl1~5, sptDscrptDocUrl1~3, stdNtceDocUrl)를
 * BidAttachment 목록으로 변환한다. 첨부파일 API 응답 전/실패 시 대체 목록으로 사용한다.
 */
export function legacyAttachmentsFromBid(bid: BidItem): BidAttachment[] {
  const record = bid as unknown as Record<string, string | undefined>;

  const ntceSpecDocs = range(NTCE_SPEC_DOC_COUNT).map((i) =>
    legacyItem(record[`ntceSpecDocUrl${i}`], record[`ntceSpecFileNm${i}`], '공고규격서', `공고규격서 ${i}`, i),
  );
  const sptDscrptDocs = range(SPT_DSCRPT_DOC_COUNT).map((i) =>
    legacyItem(record[`sptDscrptDocUrl${i}`], record[`sptDscrptFileNm${i}`], '현장설명서', `현장설명서 ${i}`, i),
  );
  const stdNtceDoc = legacyItem(bid.stdNtceDocUrl, bid.stdNtceDocFileNm, '표준공고서', '표준공고서', null);

  return [...ntceSpecDocs, ...sptDscrptDocs, stdNtceDoc].filter(
    (item): item is BidAttachment => item !== null,
  );
}
