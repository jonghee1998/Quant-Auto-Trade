import Link from 'next/link';
import { Connecting, Planned, TabBar, MarketSeg } from '../../components/ui';
import { getMarket } from '../../lib/source';
import TrendList from './TrendList';

export const dynamic = 'force-dynamic'; // 배포 때 만든 예시 화면을 재사용하지 않고 요청마다 DB에서 읽는다

export default async function Trend() {
  const d = await getMarket();
  return (
    <main className="page">
      <div className="head"><h1>시장</h1><Link href="/data" className="sub">{d.asOf} 기준</Link></div>
      <MarketSeg on="trend" />
      <Planned title="관심 종목" note="종목 상세의 ★로 담아 두면 여기에 1개월 수익률과 장기 추세(200일선 위/아래)가 항상 떠요." />
      <Planned title="이번 달 데이터가 고른 것" note="실험실에서 검증을 통과한 전략이 생기면, 그 전략이 고른 좋은 3·나쁜 3과 이유가 여기에 떠요." />
      {d.sample ? <Connecting reason={d.sampleReason} /> : <TrendList universe={d.universe} bench={d.bench} />}
      <div style={{ margin: '12px 16px 0' }}><input type="search" placeholder="목록에 없는 종목 찾기 (전 종목)" aria-label="종목 검색" /></div>
      <TabBar on="market" />
    </main>
  );
}
