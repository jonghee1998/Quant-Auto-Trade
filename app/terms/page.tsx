import { Back } from '../../components/ui';
import { TERMS } from '../../lib/terms';

export default function Terms() {
  return (
    <main className="page">
      <Back href="/" label="시장" />
      <div className="head" style={{ paddingTop: 0 }}><h1>용어 풀이</h1></div>
      <section className="card">
        {TERMS.map(([t, d]) => <div key={t} className="row" style={{ display: 'block' }}><div className="b" style={{ fontSize: 14 }}>{t}</div><div style={{ fontSize: 13, color: '#3F3F46', lineHeight: 1.5 }}>{d}</div></div>)}
      </section>
    </main>
  );
}
