import { Back, Connecting, TabBar } from '../../components/ui';
import { pct } from '../../lib/format';
import { getLab } from '../../lib/lab';
import { ROUNDS, roundIds, sortCards, verdictOf, type LabRow, type Round, type Verdict } from '../../lib/labRounds';

export const dynamic = 'force-dynamic';

const REPO = 'https://github.com/jonghee1998/Quant-Auto-Trade/issues/';
const TAG: Record<Verdict, string> = { 후보: 'ok', 보류: 'warn', 탈락: '' };
const p = (v: number | null, d = 1) => pct(v == null ? null : v * 100, d);

function Line({ r, label }: { r: LabRow; label: string }) {
  return (
    <div className="sub" style={{ marginTop: 3 }}>
      {label} · {r.liq ? '세후' : '연'} <b className={r.ret != null && r.benchRet != null && r.ret > r.benchRet ? 'up' : ''}>{p(r.ret)}</b>
      {' '}(S&amp;P {p(r.benchRet)}) · 최악 <b>{p(r.mdd, 0)}</b> (S&amp;P {p(r.benchMdd, 0)}){r.trades != null ? ` · 매매 ${r.trades}회` : ''}
    </div>
  );
}

function RoundCard({ round, rows }: { round: Round; rows: LabRow[] }) {
  const mine = rows.filter((r) => (round.plan == null ? r.plan == null : r.plan === round.plan) && roundIds(round).includes(r.id));
  const ids = roundIds(round);
  const cards = sortCards(ids.map((id) => {
    const dev = mine.find((r) => r.id === id && r.period === 'dev') ?? null;
    const valid = mine.find((r) => r.id === id && r.period === 'valid') ?? null;
    const vd = verdictOf(round, id);
    const gap = dev && dev.ret != null && dev.benchRet != null ? dev.ret - dev.benchRet : null;
    return { id, dev, valid, v: vd?.v ?? null, why: vd?.why ?? '', gap };
  }).filter((c) => c.dev || c.valid));
  const n = { 후보: 0, 보류: 0, 탈락: 0 } as Record<Verdict, number>;
  for (const c of cards) if (c.v) n[c.v]++;
  const list = cards.map((c) => (
    <div key={c.id} className="row" style={{ display: 'block' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 14 }}><b>{c.id}</b> <span className="sub">{(c.dev ?? c.valid)?.hypothesis}</span></span>
        {c.v && <span className={`tag ${TAG[c.v]}`} style={{ flexShrink: 0 }}>{c.v}</span>}
      </div>
      {c.dev && <Line r={c.dev} label="개발 2010~17" />}
      {c.valid && <Line r={c.valid} label="검증 2018~22" />}
      {c.why && <div className="sub" style={{ marginTop: 3, color: 'var(--ink)' }}>{c.why}</div>}
    </div>
  ));
  return (
    <section className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <h2>{round.round}차 · {round.title}</h2>
        <span className={`tag ${n.후보 ? 'ok' : ''}`} style={{ flexShrink: 0 }}>후보 {n.후보}</span>
      </div>
      <div className="sub" style={{ marginTop: 4, lineHeight: 1.5 }}><b>알아보려던 것</b> · {round.question}</div>
      <div style={{ marginTop: 6, fontSize: 14, lineHeight: 1.5 }}>{round.conclusion}</div>
      <div className="sub" style={{ marginTop: 8, lineHeight: 1.6 }}>
        <b>알게 된 것</b>
        {round.learned.map((x) => <div key={x}>· {x}</div>)}
        <b style={{ display: 'block', marginTop: 4 }}>다음에 볼 것</b>
        {round.next.map((x) => <div key={x}>· {x}</div>)}
      </div>
      <div className="sub" style={{ marginTop: 6 }}>
        {round.planIssue ? <><a href={REPO + round.planIssue}>Fable 설계 #{round.planIssue}</a> · </> : 'Fable 설계 없음 · '}
        <a href={REPO + round.judgeIssue}>Fable 판정 #{round.judgeIssue}</a>
        {' '}· 보류 {n.보류} · 탈락 {n.탈락}
      </div>
      {cards.length === 0 ? <div className="sub" style={{ marginTop: 8 }}>실험 기록을 아직 못 읽었어요.</div>
        : round.round === ROUNDS[0].round ? <div style={{ marginTop: 6 }}>{list}</div>
          : <details style={{ marginTop: 8 }}><summary className="sub">실험 {cards.length}개 보기</summary>{list}</details>}
    </section>
  );
}

export default async function LabPage() {
  const rows = await getLab();
  return (
    <main className="page">
      <Back href="/invest" label="투자" />
      <div className="head" style={{ paddingTop: 0, display: 'block' }}>
        <h1>실험실</h1>
        <p className="sub" style={{ margin: '4px 0 0', lineHeight: 1.5 }}>
          Fable이 설계하고 판정해요. 비교 대상은 S&amp;P 500 그냥 보유. 후보가 나오면 사람 승인 뒤 홀드아웃(2023~)을 한 번 열어요.
        </p>
      </div>
      {!rows && <Connecting reason="실험 기록을 못 읽었어요" />}
      {ROUNDS.map((r) => <RoundCard key={r.round} round={r} rows={rows ?? []} />)}
      <section className="card" style={{ fontSize: 12, lineHeight: 1.6 }}>
        <div className="sub">세후 = 마지막 날 다 팔고 양도세(250만 원 공제 뒤 22%)·배당세 15%·수수료·환전까지 낸 뒤의 연수익(2차부터, 1억 원 기준). 1차는 세금 전 연수익. 최악 손실 = 고점에서 가장 크게 빠진 폭.</div>
      </section>
      <TabBar on="invest" />
    </main>
  );
}
