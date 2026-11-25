'use client';
import { useState } from 'react';
import { EXPERIMENTS, BACKTEST, PAPER } from '../../lib/mock';
import { won, pct } from '../../lib/format';

const STATUS_TAG: Record<string, string> = { '모의투자로 감': 'ok', '후보': 'down', '탈락': '' };

function Lab() {
  const [idea, setIdea] = useState('');
  const [sent, setSent] = useState(false);
  return (
    <>
      <section className="card">
        <label htmlFor="idea" className="b" style={{ fontSize: 15 }}>내 아이디어 넣기</label>
        <textarea id="idea" rows={2} value={idea} onChange={(e) => { setIdea(e.target.value); setSent(false); }} placeholder="금리가 내려가기 시작하면 소형주가 대형주보다 낫지 않을까?" style={{ marginTop: 8, resize: 'none' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
          <span className="sub">{sent ? '프로토타입: 실제로 보내지 않았어요' : 'Fable이 먼저 검토하고 시험 계획을 짜요'}</span>
          <button type="button" className="btn" onClick={() => setSent(idea.trim().length > 0)}>검토 요청</button>
        </div>
      </section>
      <section className="card" style={{ fontSize: 13, lineHeight: 1.6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><span className="b" style={{ fontSize: 15 }}>Fable 검토 · 금리 내리면 소형주</span><span className="tag down">시험할 만함</span></div>
        <div><span className="sub">다듬은 가설</span> · 기준금리 인하가 시작되면 6개월간 소형주(IWM)가 S&amp;P를 앞선다</div>
        <div><span className="sub">주의</span> · 인하 시작이 적어(2010년 이후 4번) 우연일 수 있음. 금리 발표일 기준으로만 신호</div>
        <div><span className="sub">시험 계획</span> · 월 1회, IWM↔SPY, 비용·세금 포함, 기존 전략과 겹치는지 비교</div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}><button type="button" className="btn" style={{ flex: 1 }}>이대로 시험</button><button type="button" className="btn ghost" style={{ flex: 1 }}>고쳐서 다시</button></div>
      </section>
      <div className="card" style={{ background: 'transparent', border: '1px solid var(--edge)', fontSize: 12 }}>
        <b>자동 실험 켜짐</b> · 매주 월요일 Fable이 새 가설 2개를 내고 시험 · 이번 달 시도 23/50 (시도가 많을수록 통과 기준이 높아져요)
      </div>
      <h2 style={{ margin: '16px 16px 0', fontSize: 15 }}>실험 결과</h2>
      {EXPERIMENTS.map((x) => (
        <section key={x.title} className="card" style={{ fontSize: 13, lineHeight: 1.55 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}><span className="b" style={{ fontSize: 16 }}>{x.title}</span><span className={`tag ${STATUS_TAG[x.status] ?? ''}`}>{x.status}</span></div>
          <div style={{ marginTop: 6 }}><span className="sub">알아보려던 것</span> · {x.goal}</div>
          <div><span className="sub">쓴 방법</span> · {x.used}</div>
          <div className="cmp" style={{ background: 'var(--bg)', borderRadius: 8, padding: '8px 10px', marginTop: 8, fontSize: 12 }}>
            <span /><span className="sub">내 전략</span><span className="sub">S&amp;P 그냥 보유</span>
            <span className="sub">연 수익</span><b>{pct(x.me.cagr)}</b><span>{pct(x.spy.cagr)}</span>
            <span className="sub">최악 손실</span><b className="down">{pct(x.me.mdd, 0)}</b><span className="down">{pct(x.spy.mdd, 0)}</span>
          </div>
          <div style={{ marginTop: 8 }}><span className="sub">알게 된 것</span> · <b>{x.insight}</b></div>
          <div className="sub">다음 · {x.next}</div>
        </section>
      ))}
    </>
  );
}

function Backtest() {
  const b = BACKTEST;
  return (
    <>
      <section className="card">
        <div className="sub">전략</div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}><span className="b" style={{ fontSize: 17 }}>{b.name}</span><span className="tag down">후보</span></div>
        <div className="sub" style={{ marginTop: 2 }}>{b.logic}</div>
        <div className="cmp" style={{ marginTop: 12 }}>
          <span /><span className="sub">이 전략</span><span className="sub">S&amp;P 보유</span>
          {b.rows.map(([k, a, c]) => [<span key={k + 'k'} className="sub">{k}</span>, <b key={k + 'a'}>{a}</b>, <span key={k + 'c'}>{c}</span>])}
        </div>
        <div className="muted" style={{ marginTop: 6 }}>“내린 달 빠짐 61%” = 시장이 10% 빠진 달에 평균 6.1%만 빠졌다는 뜻. 세후·원화, 2010년~.</div>
      </section>
      <section className="card" style={{ fontSize: 13, lineHeight: 1.7 }}>
        <h2>후보 기준</h2>
        {b.checks.map(([ok, t]) => <div key={t} style={{ color: ok ? 'var(--ink)' : 'var(--sub)' }}>{ok ? '✓' : '✗'} {t}</div>)}
      </section>
      <section className="card" style={{ fontSize: 13 }}>
        <h2>힘들었던 때</h2>
        {b.stress.map(([k, me, spy]) => <div key={k} className="row"><span>{k}</span><span><b className="down">{pct(me, 0)}</b> <span className="sub">S&amp;P {pct(spy, 0)}</span></span></div>)}
      </section>
      <div className="card" style={{ background: 'transparent', border: '1px solid var(--edge)', fontSize: 12, lineHeight: 1.6 }}>
        <b>누수 막는 장치</b> · 그날까지 알 수 있던 값만(재무는 공시일, 지표는 발표일) · 신호는 다음 날 체결 · 사라진 종목도 포함 · 비용·세금·환율 반영 · 최종 구간은 전략당 한 번만 · 모든 시도 기록
      </div>
    </>
  );
}

function Invest() {
  const p = PAPER;
  const r = (p.value / p.capital - 1) * 100, s = (p.spyValue / p.capital - 1) * 100;
  return (
    <>
      <section className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div><div className="sub">실제 투자</div><div className="b" style={{ fontSize: 15 }}>꺼짐 · 대신 모의투자를 보여줘요</div></div><span className="tag">모의</span>
      </section>
      <section className="card dark">
        <div className="sub">돌리는 전략</div>
        <div className="b" style={{ fontSize: 17 }}>{p.name}</div>
        <div className="sub" style={{ marginTop: 4 }}>{p.start} 시작 · 가상 {won(p.capital)} · 매매 {p.trades}회</div>
        <div className="grid2" style={{ marginTop: 10 }}>
          <div><div className="sub">이 전략</div><div className="b" style={{ fontSize: 18 }}>{won(p.value)}</div><div style={{ color: '#FF8A80', fontSize: 12 }}>{pct(r)}</div></div>
          <div><div className="sub">S&amp;P 그냥 산 사람</div><div className="b" style={{ fontSize: 18 }}>{won(p.spyValue)}</div><div style={{ color: '#FF8A80', fontSize: 12 }}>{pct(s)}</div></div>
        </div>
      </section>
      <section className="card" style={{ fontSize: 13 }}>
        <h2>백테스트대로 돌고 있나</h2>
        <div className="sub">모의투자의 목적은 실력 판정이 아니라 실행 확인이에요</div>
        {p.checks.map(([k, v]) => <div key={k} className="row"><span>{k}</span><b>{v}</b></div>)}
        <div className="bar" style={{ marginTop: 8 }}><div style={{ width: `${(p.trades / p.target) * 100}%`, height: 8, borderRadius: 4, background: 'var(--ink)' }} /></div>
        <div className="muted" style={{ marginTop: 4 }}>실전 전환 조건: 3개월 또는 매매 {p.target}회 중 긴 쪽 · 지금 {p.trades}/{p.target}회</div>
      </section>
      <section className="card" style={{ fontSize: 13 }}>
        <h2>매매 기록</h2>
        {p.log.map(([what, price, why]) => <div key={what} className="row" style={{ display: 'block' }}><div style={{ display: 'flex', justifyContent: 'space-between' }}><span>{what}</span><span>{price}</span></div><div className="muted">이유: {why}</div></div>)}
      </section>
      <section className="card" style={{ fontSize: 13, lineHeight: 1.6 }}>
        <h2>실제 투자 켜기</h2>
        <div>✓ 백테스트 후보 기준 통과</div><div className="sub">○ 모의 실행 확인 ({p.trades}/{p.target}회)</div><div className="sub">○ 한도: 1회 주문 · 하루 손실 · 총 투입액</div><div className="sub">○ 본인 승인</div>
        <div className="sub" style={{ marginTop: 6 }}>켜지면 이 자리에 실제 평가액·주문 로그·한도 게이지와 <b style={{ color: '#8C2017' }}>전체 정지</b> 버튼이 나와요.</div>
      </section>
    </>
  );
}

export default function InvestTabs() {
  const [tab, setTab] = useState(0);
  return (
    <>
      <div className="seg">
        {['실험실', '백테스트', '투자'].map((l, i) => <button key={l} type="button" className={tab === i ? 'on' : ''} onClick={() => setTab(i)}>{l}</button>)}
      </div>
      {tab === 0 && <Lab />}
      {tab === 1 && <Backtest />}
      {tab === 2 && <Invest />}
      <section className="card" style={{ fontSize: 13, lineHeight: 1.6 }}>
        <h2>세금·수수료 (미장 기준)</h2>
        <div className="sub">미국에 상장된 ETF·주식을 원화로 환전해서 삽니다.</div>
        <div style={{ marginTop: 6 }}><b>수익 세금</b> · 1년 동안 판 이익에서 250만 원 빼고 22%. 다음 해 5월 신고. 손실은 다음 해로 안 넘어감</div>
        <div><b>배당</b> · 미국에서 15% 떼고 들어옴</div>
        <div><b>수수료·환전</b> · 실제 증권사 요율 확인 전까지 임시값(0.05%·0.1%)</div>
        <div className="sub" style={{ marginTop: 6 }}>숫자는 모두 이걸 뺀 값. 세금은 계좌 규모에 따라 달라서 규모를 넣어 계산해요. 한국 상장 미국 ETF는 이익에 15.4%라 계산이 달라요.</div>
      </section>
    </>
  );
}
