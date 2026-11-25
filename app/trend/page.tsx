import Link from 'next/link';
import { Proto, TabBar, MarketSeg } from '../../components/ui';
import { WATCH, PICKS } from '../../lib/mock';
import { getMarket } from '../../lib/source';
import { pct, tone } from '../../lib/format';
import TrendList from './TrendList';

function Pick({ p, up }: { p: { code: string; name: string; why: string }; up: boolean }) {
  return (
    <Link href={`/stock/${p.code}`} className="row" style={{ justifyContent: 'flex-start' }}>
      <span className={`tag ${up ? 'up' : 'down'}`}>{up ? '▲' : '▼'}</span>
      <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 14 }}>{p.name} <span className="muted">{p.code}</span></div><div className="sub">{p.why}</div></div>
    </Link>
  );
}

export const revalidate = 600;

export default async function Trend() {
  const d = await getMarket();
  return (
    <main className="page">
      <Proto sample={d.sample} />
      <div className="head"><h1>시장</h1><Link href="/data" className="sub">{d.asOf} 기준</Link></div>
      <MarketSeg on="trend" />
      <section className="card" style={{ paddingBottom: 4 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><h2>관심 종목</h2><span className="sub">1개월 · 장기 추세</span></div>
        {WATCH.map((w) => (
          <Link key={w.code} href={`/stock/${w.code}`} className="row">
            <span style={{ color: '#E0A100' }} aria-hidden="true">★</span>
            <div style={{ flex: 1 }}><div style={{ fontSize: 14 }}>{w.name}</div><div className="muted">{w.code} · {w.meta}</div></div>
            <span className={`${tone(w.m1)} b`}>{pct(w.m1)}</span>
            <span className={`tag ${w.above ? 'up' : 'down'}`}>{w.above ? '추세 위' : '추세 아래'}</span>
          </Link>
        ))}
      </section>
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><h2>이번 달 데이터가 고른 것</h2>{!PICKS.verified && <span className="tag warn">검증 전 · 참고만</span>}</div>
        <div className="sub" style={{ marginTop: 2 }}>기준 전략: {PICKS.strategy} · {PICKS.note}</div>
        <div className="b up" style={{ fontSize: 13, marginTop: 10 }}>좋은 3</div>
        {PICKS.good.map((p) => <Pick key={p.code} p={p} up />)}
        <div className="b down" style={{ fontSize: 13, marginTop: 10 }}>나쁜 3</div>
        {PICKS.bad.map((p) => <Pick key={p.code} p={p} up={false} />)}
      </section>
      <TrendList universe={d.universe} bench={d.bench} />
      <div style={{ margin: '12px 16px 0' }}><input type="search" placeholder="목록에 없는 종목 찾기 (전 종목)" aria-label="종목 검색" /></div>
      <TabBar on="market" />
    </main>
  );
}
