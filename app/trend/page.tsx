import Link from 'next/link';
import { Connecting, Planned, TabBar, MarketSeg } from '../../components/ui';
import WatchList from './WatchList';
import { getMarket } from '../../lib/source';
import TrendList from './TrendList';

export const dynamic = 'force-dynamic'; // 배포 때 만든 화면을 재사용하지 않고 요청마다 DB에서 읽는다

export default async function Trend({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = '' } = await searchParams;
  const d = await getMarket();
  const query = q.trim().toLowerCase().slice(0, 40);
  const found = query ? d.universe.filter((u) => u.name.toLowerCase().includes(query) || u.code.toLowerCase().includes(query)).slice(0, 20) : [];
  return (
    <main className="page">
      <div className="head"><h1>시장</h1><Link href="/data" className="sub">{d.asOf} 기준</Link></div>
      <MarketSeg on="trend" />
      {!d.sample && <WatchList universe={d.universe} why={d.ai.why ?? {}} />}
      <Planned title="이번 달 데이터가 고른 것" note="실험실에서 검증을 통과한 전략이 생기면, 그 전략이 고른 좋은 3·나쁜 3과 이유가 여기에 떠요." />
      {d.sample ? <Connecting reason={d.sampleReason} /> : <TrendList universe={d.universe} bench={d.bench} coverage={d.coverage} why={d.ai.why ?? {}} />}
      <form action="/trend" style={{ margin: '12px 16px 0' }}>
        <input type="search" name="q" defaultValue={q} placeholder="종목 이름·코드로 찾기" aria-label="종목 검색" />
      </form>
      {query && (
        <section className="card">
          <h2>‘{q}’ 찾기 결과 {found.length}개</h2>
          {found.length === 0 && <div className="sub" style={{ marginTop: 6 }}>화면 목록(한국은 거래대금 상위, 미국은 대표 목록)에 없어요.</div>}
          {found.map((u) => (
            <Link key={u.market + u.code} href={`/stock/${u.code}?m=${u.market}`} className="row">
              <span style={{ fontSize: 14 }}>{u.name} <span className="sub">{u.code} · {u.market === 'KR' ? '한국' : u.market === 'W' ? '나라별' : '미국'}</span></span>
              <span className="sub">›</span>
            </Link>
          ))}
        </section>
      )}
      <TabBar on="market" />
    </main>
  );
}
