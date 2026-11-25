import { Proto, TabBar } from '../../components/ui';
import InvestTabs from './InvestTabs';

export default function InvestPage() {
  return (
    <main className="page">
      <Proto />
      <div className="head" style={{ display: 'block' }}>
        <h1>투자</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>목표: 잃을 땐 조금, 벌 땐 많이 · S&amp;P 500 그냥 보유보다 낫게</p>
      </div>
      <InvestTabs />
      <TabBar on="invest" />
    </main>
  );
}
