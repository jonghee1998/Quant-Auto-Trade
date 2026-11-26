import { Back, Connecting } from '../../components/ui';
import { getStatus, sourceName } from '../../lib/status';

export const dynamic = 'force-dynamic';

const FREE_DB = 512 * 1024 * 1024; // Neon 무료 저장 공간

export default async function DataPage() {
  const s = await getStatus();
  return (
    <main className="page">
      <Back href="/" label="시장" />
      <div className="head" style={{ paddingTop: 0 }}><h1>데이터 상태</h1></div>
      {!s ? <Connecting reason="수집 기록을 못 읽었어요" /> : <>
        <section className="card">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 8, fontSize: 13 }}>
            <div><div className="sub">화면 데이터</div><div className="b">{s.briefDate ?? '—'}</div></div>
            <div><div className="sub">AI 글</div><div className="b">{s.aiAt ? s.aiAt.slice(5, 16).replace('T', ' ') : '아직'}</div></div>
            <div><div className="sub">저장 공간</div><div className="b">{s.dbBytes == null ? '—' : `${Math.round(s.dbBytes / 1048576)}MB`}</div>
              <div className="sub">무료 512MB 중 {s.dbBytes == null ? '—' : `${Math.round((s.dbBytes / FREE_DB) * 100)}%`}</div></div>
          </div>
        </section>
        <section className="card">
          <h2>소스별 최근 7일</h2>
          <div className="sub" style={{ marginTop: 2 }}>● 성공 · ● 실패 · ○ 실행 없음 (왼쪽이 6일 전)</div>
          {s.sources.map((x) => (
            <div key={x.source} className="row" style={{ display: 'block' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14 }}>{sourceName(x.source)}</span>
                <span style={{ display: 'flex', gap: 4 }} aria-label="최근 7일">
                  {x.days.map((d) => <span key={d.day} title={d.day} style={{ width: 10, height: 10, borderRadius: 5, border: '1px solid var(--edge)', background: d.ok === null ? 'transparent' : d.ok ? 'var(--ok)' : 'var(--up)' }} />)}
                </span>
              </div>
              <div className="sub" style={{ marginTop: 3 }}>
                마지막 {x.lastAt} · {x.lastStatus === 'ok' ? '성공' : x.lastStatus === 'failed' ? '실패' : `일부 실패 ${x.failedLast}/${x.jobsLast}`} · {x.lastRows.toLocaleString()}건
              </div>
              {x.lastError && <div className="sub" style={{ marginTop: 3, color: 'var(--up)', wordBreak: 'break-all' }}>확인할 것: {x.lastError}</div>}
            </div>
          ))}
          {s.sources.length === 0 && <div className="sub" style={{ marginTop: 6 }}>최근 7일 수집 기록이 없어요.</div>}
        </section>
      </>}
    </main>
  );
}
