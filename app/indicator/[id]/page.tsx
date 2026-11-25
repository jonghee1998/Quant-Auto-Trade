import Link from 'next/link';
import { Proto, Back } from '../../../components/ui';
import { QUOTES } from '../../../lib/mock';
import { num, pct } from '../../../lib/format';

const RELATED = [['금융 여건 (NFCI)', '−0.48 · 느슨함'], ['VIX 단기/중기', '0.92 · 정상'], ['하이일드 스프레드', '안정 (상태만 표시)'], ['장단기 금리차 (10년−3개월)', '+0.38%p']];

export default async function Indicator({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const q = QUOTES.find((x) => x.id === id);
  return (
    <main className="page">
      <Proto />
      <Back href="/" label="시장" />
      <div style={{ padding: '0 16px' }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>{q?.name ?? id}</h1>
        <div className="b" style={{ fontSize: 28, marginTop: 4 }}>{num(q?.value, id === 'vix' ? 1 : 0)}{q?.unit ?? ''}</div>
        <div className="sub">{q?.note ?? `한 달 ${pct(q?.m1)} · 1년 ${pct(q?.y1, 0)}`}</div>
      </div>
      <section className="card" style={{ fontSize: 13 }}>
        <h2>통계</h2>
        <div className="sub" style={{ marginTop: 4 }}>1년 중 위치 · 10년 평균 · 최고/최저 — 데이터 연결 후 계산</div>
      </section>
      <section className="card" style={{ paddingTop: 0, paddingBottom: 0 }}>
        {RELATED.map(([k, v]) => <div key={k} className="row" style={{ fontSize: 14 }}><span>{k}</span><span className="sub">{v}</span></div>)}
      </section>
      <div className="muted" style={{ margin: '12px 16px 0' }}>출처: FRED(발표일 기준). 백테스트는 발표일 이후에만 이 값을 씁니다. <Link href="/terms">용어 풀이</Link></div>
    </main>
  );
}
