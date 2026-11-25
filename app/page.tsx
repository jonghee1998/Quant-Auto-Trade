import Link from 'next/link';
import { Proto, TabBar, MarketSeg, Signed } from '../components/ui';
import { getMarket } from '../lib/source';
import { num, pct, moveLabel } from '../lib/format';

export const revalidate = 600;

export default async function Today() {
  const d = await getMarket();
  const { asOf: AS_OF, quotes: QUOTES, summary: SUMMARY, trendLight: TREND_LIGHT, breadth: BREADTH, news: NEWS } = d;
  const green = TREND_LIGHT.state === 'green';
  return (
    <main className="page">
      <Proto sample={d.sample} />
      <div className="head">
        <h1>시장</h1>
        <Link href="/data" className="sub" style={{ display: 'flex', alignItems: 'center', gap: 6, height: 44 }}>
          <span className="dot" style={{ background: 'var(--ok)', borderRadius: 5 }} />{AS_OF} 기준
        </Link>
      </div>
      <MarketSeg on="today" />
      <section className="card dark">
        <div className="sub">오늘 한 줄</div>
        <p style={{ margin: '4px 0 0', fontSize: 17, fontWeight: 700, lineHeight: 1.5 }}>{SUMMARY}</p>
      </section>
      <section className="card" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <span style={{ width: 36, height: 36, borderRadius: 18, background: green ? '#E5F4EA' : '#FDECEA', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ width: 14, height: 14, borderRadius: 7, background: green ? 'var(--ok)' : 'var(--up)' }} />
        </span>
        <div>
          <div className="b" style={{ fontSize: 15 }}>시장 추세 신호등: {TREND_LIGHT.state === null ? '—' : green ? '초록' : '빨강'}</div>
          <div className="sub">S&amp;P 500이 200일 평균선보다 {pct(TREND_LIGHT.gapPct)} · {BREADTH.total}개 업종 중 {BREADTH.above}개가 장기 추세 위</div>
        </div>
      </section>
      <section className="card" style={{ paddingTop: 2, paddingBottom: 2 }}>
        <div className="muted" style={{ paddingTop: 10 }}>오늘 변화 옆 표시: 평소 하루 움직임과 비교</div>
        {QUOTES.map((q) => {
          const label = moveLabel(q.change, q.dailyStd);
          const warn = q.id === 'vix' && (q.value ?? 0) >= 20;
          return (
            <Link key={q.id} href={`/indicator/${q.id}`} className="row" style={{ display: 'block' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 15 }}>{q.name}</span>
                <span className="b" style={{ fontSize: 15 }}>{num(q.value, q.id === 'vix' ? 1 : 0)}{q.unit ?? ''}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                <span className="sub">{q.note ?? `한 달 ${pct(q.m1)} · 1년 ${pct(q.y1, 0)}`}</span>
                <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Signed v={q.change} text={q.changeText ?? pct(q.change)} />
                  <span className={`tag ${warn ? 'warn' : ''}`}>{warn ? '조금 불안' : label}</span>
                </span>
              </div>
            </Link>
          );
        })}
      </section>
      <section className="card">
        <h2>오늘 뉴스</h2>
        {NEWS.map((n) => (
          <div key={n.title} className="row" style={{ fontSize: 14 }}>{n.title} <span className="sub">{n.where}</span></div>
        ))}
      </section>
      <TabBar on="market" />
    </main>
  );
}
