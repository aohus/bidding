import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { backendApi } from '@/lib/backendApi';
import { EstimateRateDistributionResponse } from '@/types/bid';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  query: {
    region?: string;
    industry?: string;
    industryField?: string;
    contractMethod?: string;
    presmptPrce?: number;
  };
}

type PlotDomain = {
  min: number;
  max: number;
  median: number;
};

type StripPoint = {
  rate: number;
  xPercent: number;
  lane: number;
};

const DEFAULT_RATE_DOMAIN: PlotDomain = {
  min: 0.995,
  max: 1.005,
  median: 1.0,
};

function formatPct(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '-';
  return `${(value * 100).toFixed(digits)}%`;
}

function formatPrice(value: number | null | undefined): string {
  if (value == null) return '-';
  return value.toLocaleString();
}

function formatOpengDt(raw: string | null | undefined): string {
  if (!raw || raw.length < 8) return '-';
  return `${raw.slice(0, 4)}.${raw.slice(4, 6)}.${raw.slice(6, 8)}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function buildPlotDomain(
  rates: number[],
  stats: Array<number | null | undefined>,
): PlotDomain {
  const values = [...rates, ...stats.filter((value): value is number => value != null && Number.isFinite(value))];
  if (values.length === 0) return DEFAULT_RATE_DOMAIN;

  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const rawMedian = values.slice().sort((a, b) => a - b)[Math.floor(values.length / 2)] ?? 1.0;
  const span = rawMax - rawMin;
  const paddedSpan = Math.max(span * 1.3, 0.0015);
  const center = (rawMin + rawMax) / 2;
  const min = clamp(center - paddedSpan / 2, 0.5, 1.5);
  const max = clamp(center + paddedSpan / 2, 0.5, 1.5);

  if (max <= min) return DEFAULT_RATE_DOMAIN;

  return {
    min,
    max,
    median: clamp(rawMedian, min, max),
  };
}

function toPercent(value: number, domain: PlotDomain): number {
  return ((value - domain.min) / (domain.max - domain.min)) * 100;
}

function buildStripPoints(rates: number[], domain: PlotDomain): StripPoint[] {
  const xPercents = rates
    .slice()
    .sort((a, b) => a - b)
    .map((rate) => ({
      rate,
      xPercent: clamp(toPercent(rate, domain), 0, 100),
    }));

  const laneLastX: number[] = [];
  const minGapPercent = 1.8;

  return xPercents.map(({ rate, xPercent }) => {
    let lane = laneLastX.findIndex((lastX) => xPercent - lastX >= minGapPercent);
    if (lane === -1) {
      lane = laneLastX.length;
      laneLastX.push(xPercent);
    } else {
      laneLastX[lane] = xPercent;
    }

    return {
      rate,
      xPercent,
      lane,
    };
  });
}

export default function EstimateRateDistributionDialog({ isOpen, onClose, query }: Props) {
  const [data, setData] = useState<EstimateRateDistributionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    backendApi
      .getEstimateRateDistribution({ ...query, limit: 200 })
      .then((res) => {
        if (cancelled) return;
        setData(res);
      })
      .catch(() => {
        if (cancelled) return;
        setError('분포 데이터를 불러오지 못했습니다');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, query.region, query.industry, query.industryField, query.contractMethod, query.presmptPrce]);

  const rates = data?.items.map((item) => item.reserve_rate) ?? [];
  const plotDomain = buildPlotDomain(rates, [data?.p25, data?.median_rate, data?.p75]);
  const stripPoints = buildStripPoints(rates, plotDomain);
  const maxLane = stripPoints.reduce((max, point) => Math.max(max, point.lane), 0);
  const plotHeight = Math.min(180, Math.max(132, 96 + maxLane * 9));
  const medianPercent = data?.median_rate != null ? clamp(toPercent(data.median_rate, plotDomain), 0, 100) : null;
  const p25Percent = data?.p25 != null ? clamp(toPercent(data.p25, plotDomain), 0, 100) : null;
  const p75Percent = data?.p75 != null ? clamp(toPercent(data.p75, plotDomain), 0, 100) : null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>비슷한 공고의 사정율 분포</DialogTitle>
          <DialogDescription>
            동일 그룹 키 기준 최근 60일 reserve_price 데이터
          </DialogDescription>
        </DialogHeader>

        {loading && <p className="text-sm text-muted-foreground py-8 text-center">불러오는 중…</p>}
        {error && <p className="text-sm text-red-600 py-8 text-center">{error}</p>}

        {data && !loading && !error && (
          <div className="space-y-4">
            {/* 통계 요약 */}
            <div className="grid grid-cols-4 gap-2 text-sm">
              <Stat label="표본 수" value={`${data.sample_size}건`} />
              <Stat label="평균" value={formatPct(data.avg_rate)} />
              <Stat label="중앙값" value={formatPct(data.median_rate)} />
              <Stat label="P25 ~ P75" value={`${formatPct(data.p25)} ~ ${formatPct(data.p75)}`} />
            </div>

            {/* 매칭 키 */}
            {data.matched_keys.length > 0 && (
              <div className="text-xs text-muted-foreground">
                매칭 기준: {data.matched_keys.join(' + ')}
              </div>
            )}

            {/* Strip plot */}
            {data.items.length > 0 ? (
              <div>
                <div className="flex items-center justify-between gap-3 mb-2">
                  <h3 className="text-sm font-semibold">사정율 분포</h3>
                  <span className="text-[11px] text-muted-foreground">가까운 값은 위로 쌓아 표시</span>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gradient-to-b from-slate-50 to-white px-3 py-3">
                  <div className="relative" style={{ height: `${plotHeight}px` }}>
                    {p25Percent != null && p75Percent != null && (
                      <div
                        className="absolute top-4 h-5 rounded bg-blue-100/80"
                        style={{
                          left: `${p25Percent}%`,
                          width: `${Math.max(p75Percent - p25Percent, 1)}%`,
                        }}
                        title={`IQR: ${formatPct(data.p25, 3)} ~ ${formatPct(data.p75, 3)}`}
                      />
                    )}
                    {medianPercent != null && (
                      <div
                        className="absolute top-2 w-0.5 bg-blue-700"
                        style={{ left: `${medianPercent}%`, bottom: '28px' }}
                        title={`중앙값: ${formatPct(data.median_rate, 3)}`}
                      />
                    )}
                    <div
                      className="absolute inset-x-0 border-t border-dashed border-gray-300"
                      style={{ bottom: '28px' }}
                    />
                    {stripPoints.map((point, index) => (
                      <div
                        key={`${point.rate}-${index}`}
                        className="absolute h-2 w-2 -translate-x-1/2 rounded-full border border-white/80 bg-blue-600 shadow-sm"
                        style={{
                          left: `${point.xPercent}%`,
                          bottom: `${32 + point.lane * 9}px`,
                        }}
                        title={formatPct(point.rate, 3)}
                      />
                    ))}
                    <div className="absolute inset-x-0 bottom-0 flex justify-between text-[10px] text-muted-foreground">
                      <span>{formatPct(plotDomain.min, 3)}</span>
                      <span>{formatPct(plotDomain.median, 3)}</span>
                      <span>{formatPct(plotDomain.max, 3)}</span>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2.5 w-2.5 rounded-full bg-blue-600" />
                      표본
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="h-3 w-5 rounded bg-blue-100" />
                      P25~P75
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="h-3 w-0.5 bg-blue-700" />
                      중앙값
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                분포 데이터가 없습니다
              </p>
            )}

            {/* 표본 리스트 (최근순 10건만) */}
            {data.items.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">최근 표본 (상위 10건)</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-muted-foreground border-b">
                        <th className="py-1.5 pr-2">개찰일</th>
                        <th className="py-1.5 pr-2">공고명</th>
                        <th className="py-1.5 pr-2 text-right">기초금액</th>
                        <th className="py-1.5 pr-2 text-right">예정가격</th>
                        <th className="py-1.5 text-right">사정율</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.slice(0, 10).map((item) => (
                        <tr key={`${item.bid_ntce_no}`} className="border-b border-gray-100">
                          <td className="py-1.5 pr-2 whitespace-nowrap">{formatOpengDt(item.openg_dt)}</td>
                          <td className="py-1.5 pr-2 max-w-[280px] truncate" title={item.bid_ntce_nm ?? ''}>
                            {item.bid_ntce_nm ?? '-'}
                          </td>
                          <td className="py-1.5 pr-2 text-right">{formatPrice(item.bssamt)}</td>
                          <td className="py-1.5 pr-2 text-right">{formatPrice(item.plnprc)}</td>
                          <td className="py-1.5 text-right font-semibold">{formatPct(item.reserve_rate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 bg-gray-50 rounded text-center">
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className="font-semibold text-gray-800">{value}</p>
    </div>
  );
}
