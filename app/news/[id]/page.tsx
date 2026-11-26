import { Back, Connecting } from '../../../components/ui';
import { getMarket } from '../../../lib/source';

export const dynamic = 'force-dynamic';

export default async function NewsDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await getMarket();
  const n = d.ai.news?.find((x) => x.id === id);
  return (
    <main className="page">
      <Back href="/" label="시장" />
      {!n ? <Connecting reason="이 뉴스는 더 이상 목록에 없어요" /> : <>
        <div style={{ padding: '0 16px' }}>
          <span className="tag">{n.cat}</span>
          <h1 style={{ fontSize: 20, lineHeight: 1.45, margin: '10px 0 0' }}>{n.title}</h1>
          <div className="sub" style={{ marginTop: 6 }}>{n.where} · 언론사 {n.outlets}곳 보도 · AI가 번역·요약</div>
        </div>
        <section className="card">
          <h2>3줄 요약</h2>
          <ol style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 14, lineHeight: 1.65 }}>{n.summary.map((s) => <li key={s}>{s}</li>)}</ol>
        </section>
        <section className="card">
          <h2>시장에 주는 의미</h2>
          <p style={{ fontSize: 14, lineHeight: 1.6, margin: '6px 0 0' }}>{n.meaning}</p>
        </section>
        <section className="card">
          <h2>원문</h2>
          {n.links.map((l) => (
            <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="row" style={{ fontSize: 14 }}>
              <span>{l.name}</span><span className="sub">원문 ↗</span>
            </a>
          ))}
          <div className="sub" style={{ marginTop: 6 }}>요약은 AI가 쓴 거라 틀릴 수 있어요. 중요한 판단은 원문을 확인하세요.</div>
        </section>
      </>}
    </main>
  );
}
