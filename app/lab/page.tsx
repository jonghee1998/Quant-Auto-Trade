import { Back, TabBar } from '../../components/ui';
import { pct } from '../../lib/format';
import { ROUNDS, type LabExp, type Result, type Verdict } from '../../lib/labRounds';

const REPO = 'https://github.com/jonghee1998/Quant-Auto-Trade/issues/';
const TAG: Record<Verdict, string> = { 후보: 'ok', 보류: 'warn', 탈락: '' };

function Res({ x, label }: { x: Result; label?: string }) {
  const win = x.ret > x.bench;
  return (
    <span>
      {label && <span className="sub">{label} </span>}
      연 <b className={win ? 'up' : ''}>{pct(x.ret)}</b> <span className="sub">(S&amp;P {pct(x.bench)})</span>
      {' · '}최악 <b>{pct(x.mdd, 0)}</b> <span className="sub">(S&amp;P {pct(x.benchMdd, 0)})</span>
    </span>
  );
}

function Exp({ e }: { e: LabExp }) {
  return (
    <div className="row" style={{ display: 'block' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 15 }}><b>{e.id}</b> {e.name}</span>
        <span className={`tag ${TAG[e.v]}`} style={{ flexShrink: 0 }}>{e.v}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '36px 1fr', gap: '3px 6px', marginTop: 6, fontSize: 13, lineHeight: 1.5 }}>
        <span className="sub">접근</span><span>{e.approach}</span>
        <span className="sub">결과</span>
        <span>
          <Res x={e.dev} label={e.valid ? '개발' : undefined} />
          {e.valid && <><br /><Res x={e.valid} label="검증" /></>}
          <br /><span className="sub">{e.note}</span>
        </span>
      </div>
    </div>
  );
}

export default function LabPage() {
  return (
    <main className="page">
      <Back href="/invest" label="투자" />
      <div className="head" style={{ paddingTop: 0, display: 'block' }}>
        <h1>실험실</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>Fable이 설계·판정 · 비교 대상은 S&amp;P 500 그냥 보유</p>
      </div>
      {ROUNDS.map((r) => (
        <section key={r.round} className="card">
          <h2>{r.round}차 · {r.title} <span className="sub">({r.exps.length}개)</span></h2>
          <div style={{ marginTop: 4, fontSize: 14 }}>{r.conclusion}</div>
          <div className="sub" style={{ marginTop: 4 }}>
            {r.basis} · <a href={REPO + r.judgeIssue}>판정 #{r.judgeIssue}</a>
          </div>
          {r.exps.map((e) => <Exp key={e.id} e={e} />)}
        </section>
      ))}
      <TabBar on="invest" />
    </main>
  );
}
