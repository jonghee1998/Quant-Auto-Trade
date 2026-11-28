import Link from 'next/link';
import { Planned, TabBar } from '../../components/ui';
import LabMatrix from '../../components/LabMatrix';
import { ROUNDS, labTally } from '../../lib/labRounds';

export default function InvestPage() {
  const t = labTally();
  return (
    <main className="page">
      <div className="head" style={{ display: 'block' }}>
        <h1>투자</h1>
        <p className="sub" style={{ margin: '6px 0 0' }}>목표는 잃을 땐 조금, 벌 땐 많이. 비교 대상은 S&amp;P 500 그냥 보유예요.</p>
      </div>
      <section className="card dark">
        <div className="sub">지금 기본 전략</div>
        <p style={{ margin: '4px 0 0', fontSize: 19, fontWeight: 600, letterSpacing: '-0.01em' }}>S&amp;P 500 보유 + 자동 적립</p>
        <p className="sub" style={{ marginTop: 8, lineHeight: 1.55 }}>
          실험 {t.total}개 가운데 S&amp;P 500만큼 벌면서 덜 잃는 규칙은 {t.count.후보 ? `${t.count.후보}개예요` : '아직 없어요'}. 주문은 꺼져 있어요.
        </p>
      </section>
      <Link href="/lab" className="card" style={{ display: 'block' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <h2>실험실</h2><span className="sub">{ROUNDS.length}차까지 보기 ›</span>
        </div>
        <div style={{ marginTop: 10 }}><LabMatrix light /></div>
        <div className="sub" style={{ marginTop: 8 }}>칸 하나가 실험 하나예요. 후보 {t.count.후보}, 보류 {t.count.보류}, 탈락 {t.count.탈락}</div>
        <p style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line)', fontSize: 14, lineHeight: 1.55 }}>
          <span className="b">최근 {ROUNDS[0].round}차</span> {ROUNDS[0].conclusion}
        </p>
      </Link>
      <Planned title="백테스트" note="후보 전략의 세후 연 수익, 최악 손실, 회복 기간, 오른 달과 내린 달을 따라간 정도, 힘들었던 시기 비교가 여기에 떠요." />
      <Planned title="모의투자·실제 투자" note="실제 투자는 기본으로 꺼져 있어요. 꺼져 있으면 모의투자가 신호대로 주문됐는지와 매매 기록을 보여줘요." />
      <section className="card">
        <h2>세금과 수수료</h2>
        <div className="sub" style={{ marginTop: 2 }}>미국에 상장된 ETF와 주식을 원화로 환전해서 사는 기준이에요.</div>
        <dl className="kv" style={{ margin: '10px 0 0', fontSize: 14, lineHeight: 1.55 }}>
          <dt>수익 세금</dt><dd>1년 동안 판 이익에서 250만 원을 빼고 22%. 다음 해 5월에 신고하고, 손실은 다음 해로 넘어가지 않아요.</dd>
          <dt>배당</dt><dd>미국에서 15%를 떼고 들어와요.</dd>
          <dt>수수료·환전</dt><dd>실제 증권사 요율을 확인하기 전까지 임시값(0.05%, 0.1%)으로 계산해요.</dd>
        </dl>
      </section>
      <TabBar on="invest" />
    </main>
  );
}
