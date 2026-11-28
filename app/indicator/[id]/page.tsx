import Link from 'next/link';
import { Back, Connecting, TermsLink } from '../../../components/ui';
import Spark from '../../../components/Spark';
import { getMarket } from '../../../lib/source';
import { getDetail } from '../../../lib/detail';
import { num, pct, quoteDigits } from '../../../lib/format';

export const dynamic = 'force-dynamic';

const SOURCE: Record<string, string> = {
  spx: 'Tiingo(미국 ETF 종가)', ndx: 'Tiingo(미국 ETF 종가)', korea: '금융위원회 지수시세(data.go.kr)', kosdaq: '금융위원회 지수시세(data.go.kr)',
  vkospi: '금융위원회 지수시세(data.go.kr)', usdkrw: 'FRED(발표일 기준)', vix: 'FRED(발표일 기준)',
};

export default async function Indicator({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await getMarket();
  const q = d.quotes.find((x) => x.id === id);
  const det = q ? await getDetail(`Q:${id}`) : null;
  const lv = det?.level;
  const dg = quoteDigits(id, q?.unit);
  return (
    <main className="page">
      <Back href="/" label="시장" />
      {d.sample || !q ? <Connecting reason={d.sample ? d.sampleReason : '아직 없는 지표예요'} /> : <div style={{ padding: '0 16px' }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>{q.name}</h1>
        <div className="b" style={{ fontSize: 28, marginTop: 4 }}>{num(q.value, dg)}{q.unit ?? ''}</div>
        <div className="sub">{q.note ?? `한 달 ${pct(q.m1)}, 1년 ${pct(q.y1, 0)}`}</div>
      </div>}
      {q && (det && lv ? (
        <section className="card">
          <h2>1년 흐름</h2>
          <Spark points={det.chart} />
          <div style={{ marginTop: 12 }}>
            <div className="sub">1년 중 위치 {lv.pos == null ? '—' : `${lv.pos}%`} (최저 {num(lv.low1, dg)} ~ 최고 {num(lv.high1, dg)})</div>
            <div className="bar" style={{ marginTop: 6 }}>
              {lv.pos != null && <span style={{ position: 'absolute', left: `calc(${lv.pos}% - 6px)`, top: -2, width: 12, height: 12, borderRadius: 6, background: 'var(--ink)' }} />}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 8, marginTop: 14, fontSize: 13 }}>
            <div><div className="sub">{lv.years && lv.years < 9.5 ? `${lv.years}년` : '10년'} 평균</div><div className="b">{num(lv.avg10, dg)}</div></div>
            <div><div className="sub">최고</div><div className="b">{num(lv.max10, dg)}</div></div>
            <div><div className="sub">최저</div><div className="b">{num(lv.min10, dg)}</div></div>
          </div>
        </section>
      ) : <Connecting reason="1년 흐름·통계는 다음 수집 뒤 채워져요" />)}
      {det?.related && det.related.length > 0 && (
        <section className="card">
          <h2>함께 보는 지표</h2>
          <div className="sub" style={{ marginTop: 2 }}>한 달 전과 비교</div>
          {det.related.map((r) => (
            <div key={r.id} className="row" style={{ alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}><div style={{ fontSize: 14 }}>{r.name}</div><div className="sub">{r.state}, {r.date} 발표</div></div>
              <div style={{ textAlign: 'right' }}><div className="b" style={{ fontSize: 14 }}>{num(r.value, 2)}</div><div className="sub">{r.m1 == null ? '' : `${r.m1 >= 0 ? '+' : '−'}${Math.abs(r.m1).toFixed(2)}`}</div></div>
            </div>
          ))}
        </section>
      )}
      <div className="muted" style={{ margin: '12px 16px 0' }}>출처: {SOURCE[id] ?? 'FRED'}. 백테스트는 발표일 이후에만 이 값을 씁니다.</div>
      <TermsLink />
    </main>
  );
}
