import { Planned, TabBar } from '../../components/ui';

export default function InvestPage() {
  return (
    <main className="page">
      <div className="head" style={{ display: 'block' }}>
        <h1>투자</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>목표: 잃을 땐 조금, 벌 땐 많이 · S&amp;P 500 그냥 보유보다 낫게</p>
      </div>
      <Planned title="실험실" note="실험마다 알아보려던 것 · 쓴 방법 · S&P 그냥 보유와 비교한 결과 · 알게 된 것을 카드로 보여줘요. 아이디어를 넣으면 Fable이 먼저 검토해요." />
      <Planned title="백테스트" note="후보 전략의 세후 연 수익 · 최악 손실 · 회복 기간 · 오른 달/내린 달 따라간 정도, 후보 기준 체크, 힘들었던 시기 비교." />
      <Planned title="투자" note="실제 투자는 기본 꺼짐. 꺼져 있으면 모의투자의 실행 확인(신호대로 주문됐는지·백테스트와 차이)과 매매 기록을 보여줘요." />
      <section className="card" style={{ fontSize: 13, lineHeight: 1.6 }}>
        <h2>세금·수수료 (미장 기준)</h2>
        <div className="sub">미국에 상장된 ETF·주식을 원화로 환전해서 삽니다.</div>
        <div style={{ marginTop: 6 }}><b>수익 세금</b> · 1년 동안 판 이익에서 250만 원 빼고 22%. 다음 해 5월 신고. 손실은 다음 해로 안 넘어감</div>
        <div><b>배당</b> · 미국에서 15% 떼고 들어옴</div>
        <div><b>수수료·환전</b> · 실제 증권사 요율 확인 전까지 임시값(0.05%·0.1%)으로 계산</div>
      </section>
      <TabBar on="invest" />
    </main>
  );
}
