import Link from 'next/link';
import { Back, Connecting, Planned } from '../../../components/ui';
import { getMarket } from '../../../lib/source';
import { num, pct } from '../../../lib/format';

export const dynamic = 'force-dynamic';

export default async function Indicator({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await getMarket();
  const q = d.quotes.find((x) => x.id === id);
  return (
    <main className="page">
      <Back href="/" label="시장" />
      {d.sample || !q ? <Connecting reason={d.sample ? d.sampleReason : '아직 없는 지표예요'} /> : <div style={{ padding: '0 16px' }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>{q?.name ?? id}</h1>
        <div className="b" style={{ fontSize: 28, marginTop: 4 }}>{num(q?.value, id === 'vix' ? 1 : 0)}{q?.unit ?? ''}</div>
        <div className="sub">{q?.note ?? `한 달 ${pct(q?.m1)} · 1년 ${pct(q?.y1, 0)}`}</div>
      </div>}
      <Planned title="통계" note="1년 차트와 구간 색띠, 1년 중 위치 · 10년 평균 · 최고/최저." />
      <Planned title="관련 지표" note="금융 여건(NFCI) · VIX 단기/중기 · 하이일드 스프레드(상태만) · 장단기 금리차 — 수집은 시작됐고 화면 연결 예정." />
      <div className="muted" style={{ margin: '12px 16px 0' }}>출처: FRED(발표일 기준). 백테스트는 발표일 이후에만 이 값을 씁니다. <Link href="/terms">용어 풀이</Link></div>
    </main>
  );
}
