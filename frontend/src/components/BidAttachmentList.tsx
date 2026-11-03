import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { BidAttachment, BidItem } from '@/types/bid';
import { backendApi } from '@/lib/backendApi';
import { inferBidType } from '@/lib/bidType';
import { groupAttachments, legacyAttachmentsFromBid } from '@/lib/attachments';
import { downloadDocument } from '@/lib/download';
import { Download, FileText, Loader2 } from 'lucide-react';

type FetchStatus = 'loading' | 'success' | 'error';

interface AttachmentFetchState {
  bidKey: string;
  status: FetchStatus;
  items: BidAttachment[];
}

const DEFAULT_BID_NTCE_ORD = '000';

const toBidKey = (bid: BidItem): string => `${bid.bidNtceNo}-${bid.bidNtceOrd || DEFAULT_BID_NTCE_ORD}`;

/**
 * 다이얼로그가 열려 있는 동안 공고 첨부파일을 조회한다.
 * 응답에 bidKey를 함께 저장해, 다른 공고로 전환된 뒤 도착한 이전 공고 응답은 무시한다.
 */
function useBidAttachments(bid: BidItem, isOpen: boolean) {
  const bidKey = toBidKey(bid);
  const [state, setState] = useState<AttachmentFetchState | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setState({ bidKey, status: 'loading', items: [] });

    backendApi
      .getBidAttachments(bid.bidNtceNo, bid.bidNtceOrd || DEFAULT_BID_NTCE_ORD, inferBidType(bid))
      .then((res) => {
        if (cancelled) return;
        setState({ bidKey, status: 'success', items: res.items ?? [] });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.warn('첨부파일 조회 실패, 공고 원문 서류로 대체합니다', error);
        setState({ bidKey, status: 'error', items: [] });
      });

    return () => {
      cancelled = true;
    };
    // bid 객체가 같은 공고로 재생성돼도 재조회하지 않도록 bidKey 기준으로만 반응한다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bidKey, isOpen]);

  // 현재 공고의 응답이 아직 없으면 로딩으로 간주
  const current = state?.bidKey === bidKey ? state : null;
  return { status: current?.status ?? 'loading', items: current?.items ?? [] } as const;
}

interface BidAttachmentListProps {
  bid: BidItem;
  isOpen: boolean;
}

export default function BidAttachmentList({ bid, isOpen }: BidAttachmentListProps) {
  const { status, items } = useBidAttachments(bid, isOpen);
  const legacyItems = useMemo(() => legacyAttachmentsFromBid(bid), [bid]);

  // 로딩 중·실패·빈 응답이면 공고 원문 URL(legacy) 목록을 대신 보여준다
  const isUsingApiItems = status === 'success' && items.length > 0;
  const groups = useMemo(
    () => groupAttachments(isUsingApiItems ? items : legacyItems),
    [isUsingApiItems, items, legacyItems],
  );

  if (status !== 'loading' && groups.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <h3 className="text-sm font-semibold text-gray-500">입찰 관련 서류</h3>
        {status === 'loading' && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            첨부파일 불러오는 중
          </span>
        )}
      </div>

      {status === 'error' && (
        <p className="px-1 text-xs text-amber-700">
          첨부파일 목록을 불러오지 못해 공고 원문에 포함된 서류만 표시합니다.
        </p>
      )}

      {groups.map((group) => (
        <div key={group.label} className="space-y-1">
          <p className="px-1 text-xs font-medium text-muted-foreground">{group.label}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {group.items.map((doc, index) => (
              <Button
                key={`${doc.source}-${doc.fileUrl}-${index}`}
                variant="secondary"
                className="h-10 text-xs justify-start bg-gray-100 hover:bg-gray-200"
                title={doc.fileNm}
                onClick={() => downloadDocument(doc.fileUrl, doc.fileNm)}
              >
                <FileText className="mr-2 h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{doc.fileNm}</span>
                <Download className="ml-auto h-3.5 w-3.5 shrink-0 opacity-50" />
              </Button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
