import { Back, TabBar } from '../../components/ui';
import LabMatrix from '../../components/LabMatrix';
import { pct, pp } from '../../lib/format';
import { ROUNDS, divergeSpan, labTally, type LabExp, type Result, type Round, type Verdict } from '../../lib/labRounds';

const REPO = 'https://github.com/jonghee1998/Quant-Auto-Trade/issues/';
const TAG: Record<Verdict, string> = { 후보: 'ok', 보류: 'warn', 탈락: '' };

/** S&P 대비 막대 한 줄. diff > 0 이면 S&P보다 좋음(수익은 더 높고, 최악 손실은 더 얕음). */
function Versus({ label, diff, limit, detail }: { label: string; diff: number; limit: number; detail: string }) {
  const s = divergeSpan(diff, limit);
  return (
    <>
      <div className="dv">
        <span className="sub">{label}</span>
        <span className="t" aria-hidden="true"><span className={s.good ? 'good' : 'bad'} style={{ left: `${s.left}%`, width: `${s.width}%` }} /></span>
        <span className="d" style={{ color: s.good ? 'var(--ok)' : 'var(--ink)' }}>{pp(diff)}</span>
      </div>
      <div className="muted" style={{ paddingLeft: 66 }}>{detail}</div>
    </>
  );
}

function Res({ x, label }: { x: Result; label?: string }) {
  return (
    <div style={{ marginTop: 8 }}>
      {label && <div className="muted" style={{ marginBottom: 2 }}>{label} 구간</div>}
      <Versus label="연수익" diff={x.ret - x.bench} limit={8} detail={`전략 ${pct(x.ret)}, S&P ${pct(x.bench)}`} />
      <div style={{ height: 6 }} />
      <Versus label="최악 손실" diff={x.mdd - x.benchMdd} limit={25} detail={`전략 ${pct(x.mdd, 0)}, S&P ${pct(x.benchMdd, 0)}`} />
    </div>
  );
}

function Exp({ e }: { e: LabExp }) {
  return (
    <div className="row" style={{ display: 'block', padding: '14px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div><div style={{ fontSize: 15, fontWeight: 500 }}>{e.name}</div><div className="muted">{e.id}</div></div>
        <span className={`tag ${TAG[e.v]}`} style={{ flex: 'none', marginTop: 2 }}>{e.v}</span>
      </div>
      <p className="sub" style={{ marginTop: 6, lineHeight: 1.55 }}>{e.approach}</p>
      <Res x={e.dev} label={e.valid ? '개발' : undefined} />
      {e.valid && <Res x={e.valid} label="검증" />}
      <p style={{ marginTop: 8, fontSize: 13, lineHeight: 1.55 }}>{e.note}</p>
    </div>
  );
}

function RoundCard({ r, open }: { r: Round; open: boolean }) {
  const n = { 후보: 0, 보류: 0, 탈락: 0 } as Record<Verdict, number>;
  r.exps.forEach((e) => { n[e.v] += 1; });
  return (
    <details className="card round" open={open}>
      <summary>
        <div>
          <h2>{r.round}차 {r.title}</h2>
          <div className="sub" style={{ marginTop: 2 }}>실험 {r.exps.length}개{n.후보 ? `, 후보 ${n.후보}` : ''}{n.보류 ? `, 보류 ${n.보류}` : ''}</div>
        </div>
        <span className="chev" aria-hidden="true">›</span>
      </summary>
      <p style={{ marginTop: 10, fontSize: 14, lineHeight: 1.6 }}>{r.conclusion}</p>
      <div className="muted" style={{ marginTop: 6 }}>
        {r.basis} <a href={REPO + r.judgeIssue} style={{ textDecoration: 'underline' }}>판정 #{r.judgeIssue}</a>
      </div>
      <div style={{ marginTop: 6, borderTop: '1px solid var(--line)' }}>
        {r.exps.map((e) => <Exp key={e.id} e={e} />)}
      </div>
    </details>
  );
}

export default function LabPage() {
  const t = labTally();
  return (
    <main className="page">
      <Back href="/invest" label="투자" />
      <div className="head" style={{ paddingTop: 0, display: 'block' }}>
        <h1>실험실</h1>
        <p className="sub" style={{ margin: '6px 0 0' }}>Fable이 설계하고 판정해요. 비교 대상은 S&amp;P 500 그냥 보유예요.</p>
      </div>
      <section className="card dark">
        <p style={{ fontSize: 17, fontWeight: 600, lineHeight: 1.45, letterSpacing: '-0.01em' }}>
          지금까지 {t.total}번 실험했고, S&amp;P 500을 이긴 후보는 {t.count.후보 ? `${t.count.후보}개예요` : '아직 없어요'}.
        </p>
        <div style={{ marginTop: 12 }}><LabMatrix /></div>
        <div className="sub" style={{ marginTop: 10, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          <span><i className="dot" style={{ background: '#3CCB7F', marginRight: 5 }} />후보 {t.count.후보}</span>
          <span><i className="dot" style={{ background: '#E0A63A', marginRight: 5 }} />보류 {t.count.보류}</span>
          <span><i className="dot" style={{ background: '#3A3E47', marginRight: 5, outline: '1px solid var(--dark-line)' }} />탈락 {t.count.탈락}</span>
        </div>
        <div className="sub" style={{ marginTop: 8 }}>칸 하나가 실험 하나, 왼쪽이 1차예요.</div>
      </section>
      <div className="sub" style={{ margin: '16px 16px 0', lineHeight: 1.55 }}>
        막대는 S&amp;P 500과의 차이예요. 가운데 선이 S&amp;P이고, 오른쪽 초록이면 더 좋아요(수익은 더 높고 손실은 더 얕음).
      </div>
      {ROUNDS.map((r, i) => <RoundCard key={r.round} r={r} open={i === 0} />)}
      <TabBar on="invest" />
    </main>
  );
}
