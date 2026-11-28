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
        <p className="sub" style={{ margin: '6px 0 0' }}>잃을 땐 조금, 벌 땐 많이. 기준은 S&amp;P 500 보유예요.</p>
      </div>
      <section className="card dark">
        <div className="sub">지금 기본 전략</div>
        <p className="lead" style={{ margin: '4px 0 0', fontSize: 19, fontWeight: 600, letterSpacing: '-0.01em' }}>S&amp;P 500 보유 + 자동 적립</p>
        <p className="sub" style={{ marginTop: 8, lineHeight: 1.55 }}>
          실험 {t.total}개 중 이보다 나은 규칙은 {t.count.후보 ? `${t.count.후보}개예요` : '아직 없어요'}. 주문은 꺼져 있어요.
        </p>
      </section>
      <Link href="/lab" className="card" style={{ display: 'block' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <h2>실험실</h2><span className="sub">{ROUNDS.length}차까지 보기</span>
        </div>
        <div style={{ marginTop: 10 }}><LabMatrix light /></div>
        <div className="sub" style={{ marginTop: 8 }}>칸 하나가 실험 하나. 후보 {t.count.후보}, 보류 {t.count.보류}, 탈락 {t.count.탈락}</div>
        <p style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line)', fontSize: 14, lineHeight: 1.55 }}>
          <span className="b">최근 {ROUNDS[0].round}차</span> {ROUNDS[0].conclusion}
        </p>
      </Link>
      <Planned title="백테스트" note="후보 전략의 세후 수익, 최악 손실, 회복 기간을 보여줘요." />
      <Planned title="모의투자·실제 투자" note="실제 투자는 기본으로 꺼져 있어요. 켜기 전에는 모의투자 기록을 보여줘요." />
      <section className="card">
        <h2>세금과 수수료</h2>
        <div className="sub" style={{ marginTop: 2 }}>미국 상장 ETF·주식을 원화로 환전해 사는 기준이에요.</div>
        <dl className="kv" style={{ margin: '10px 0 0', fontSize: 14, lineHeight: 1.55 }}>
          <dt>수익 세금</dt><dd>연 이익에서 250만 원을 빼고 22%. 다음 해 5월 신고, 손실 이월 없음.</dd>
          <dt>배당</dt><dd>15%를 떼고 들어와요.</dd>
          <dt>수수료·환전</dt><dd>증권사 요율 확인 전까지 임시값 0.05%, 0.1%.</dd>
        </dl>
      </section>
      <TabBar on="invest" />
    </main>
  );
}
