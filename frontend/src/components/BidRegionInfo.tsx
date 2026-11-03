import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BidItem } from '@/types/bid';
import { MapPin } from 'lucide-react';

interface BidRegionInfoProps {
  bid: BidItem;
}

const MATCH_BADGE_CLASS = 'text-[10px] px-1.5 py-0 border-transparent';

function MatchBadge({ label, className }: { label: string; className: string }) {
  return (
    <Badge variant="outline" className={`${MATCH_BADGE_CLASS} ${className}`}>
      {label}
    </Badge>
  );
}

/** 가산지역 · 공동도급 의무지역 · 부공종 정보. 모두 비어 있으면 렌더링하지 않는다. */
export default function BidRegionInfo({ bid }: BidRegionInfoProps) {
  const incntvRgnNms = bid.incntvRgnNms?.trim();
  const jntcontrctDutyRgnNms = bid.jntcontrctDutyRgnNms?.trim();
  const dutyRate = bid.rgnDutyJntcontrctRt?.trim();
  const subsiCnsttys = (bid.subsiCnsttys ?? []).filter((s) => s.nm?.trim());

  if (!incntvRgnNms && !jntcontrctDutyRgnNms && !dutyRate && subsiCnsttys.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-md flex items-center gap-2">
          <MapPin className="h-4 w-4" />
          지역·부공종 정보
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {incntvRgnNms && (
          <div
            className={`flex flex-col gap-1 sm:flex-row sm:justify-between rounded-md p-2 ${
              bid.isIncntvRgnMatch ? 'bg-emerald-50 border border-emerald-200' : ''
            }`}
          >
            <span className="text-muted-foreground shrink-0 flex items-center gap-1">
              가산지역
              {bid.isIncntvRgnMatch && (
                <MatchBadge label="내 소재지 포함" className="bg-emerald-100 text-emerald-700" />
              )}
            </span>
            <span className="font-medium sm:text-right sm:max-w-[70%]">{incntvRgnNms}</span>
          </div>
        )}

        {(jntcontrctDutyRgnNms || dutyRate) && (
          <div
            className={`flex flex-col gap-1 sm:flex-row sm:justify-between rounded-md p-2 ${
              bid.isJntcontrctDutyRgnMatch ? 'bg-violet-50 border border-violet-200' : ''
            }`}
          >
            <span className="text-muted-foreground shrink-0 flex items-center gap-1">
              공동도급 의무지역
              {bid.isJntcontrctDutyRgnMatch && (
                <MatchBadge label="내 소재지 포함" className="bg-violet-100 text-violet-700" />
              )}
            </span>
            <span className="font-medium sm:text-right sm:max-w-[70%]">
              {jntcontrctDutyRgnNms || '-'}
              {dutyRate && (
                <span className="ml-1 text-xs text-muted-foreground">(지역의무공동도급비율 {dutyRate}%)</span>
              )}
            </span>
          </div>
        )}

        {subsiCnsttys.length > 0 && (
          <div className="flex flex-col gap-1 p-2">
            <span className="text-muted-foreground">부공종</span>
            <div className="flex flex-wrap gap-1">
              {subsiCnsttys.map((s, index) => (
                <Badge key={`${s.nm}-${index}`} variant="secondary" className="text-xs font-normal">
                  {s.nm}
                  {s.evlRt && <span className="ml-1 text-muted-foreground">평가비율 {s.evlRt}%</span>}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
