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
    contractMethod?: string;
    presmptPrce?: number;
  };
}

const HISTOGRAM_BINS = 12;
const RATE_MIN = 0.85;
const RATE_MAX = 1.15;

function buildHistogram(rates: number[]): { binStart: number; binEnd: number; count: number }[] {
  const step = (RATE_MAX - RATE_MIN) / HISTOGRAM_BINS;
  const bins = Array.from({ length: HISTOGRAM_BINS }, (_, i) => ({
    binStart: RATE_MIN + i * step,
    binEnd: RATE_MIN + (i + 1) * step,
    count: 0,
  }));
  for (const r of rates) {
    const idx = Math.min(
      HISTOGRAM_BINS - 1,
      Math.max(0, Math.floor((r - RATE_MIN) / step)),
    );
    bins[idx].count += 1;
  }
  return bins;
}

function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '-';
  return `${(value * 100).toFixed(2)}%`;
}

function formatPrice(value: number | null | undefined): string {
  if (value == null) return '-';
  return value.toLocaleString();
}

function formatOpengDt(raw: string | null | undefined): string {
  if (!raw || raw.length < 8) return '-';
  return `${raw.slice(0, 4)}.${raw.slice(4, 6)}.${raw.slice(6, 8)}`;
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
  }, [isOpen, query.region, query.industry, query.contractMethod, query.presmptPrce]);

  const histogram = data?.items ? buildHistogram(data.items.map((it) => it.reserve_rate)) : [];
  const maxCount = histogram.reduce((m, b) => Math.max(m, b.count), 0) || 1;

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

            {/* 히스토그램 */}
            {data.items.length > 0 ? (
              <div>
                <h3 className="text-sm font-semibold mb-2">사정율 분포 (히스토그램)</h3>
                <div className="flex items-end gap-1 h-32 border-b border-l border-gray-200 px-2">
                  {histogram.map((bin, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`${formatPct(bin.binStart)} ~ ${formatPct(bin.binEnd)}: ${bin.count}건`}>
                      <div
                        className="w-full bg-blue-500 rounded-t"
                        style={{ height: `${(bin.count / maxCount) * 100}%` }}
                      />
                    </div>
                  ))}
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground mt-1 px-2">
                  <span>{formatPct(RATE_MIN)}</span>
                  <span>{formatPct((RATE_MIN + RATE_MAX) / 2)}</span>
                  <span>{formatPct(RATE_MAX)}</span>
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
