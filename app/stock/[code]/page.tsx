import Link from 'next/link';
import { Proto, Back } from '../../../components/ui';
import { UNIVERSE, BENCH } from '../../../lib/mock';
import { pct, pp, tone } from '../../../lib/format';

export default async function Stock({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const item = UNIVERSE.find((i) => i.code === code);
  const r = item?.r ?? [null, null, null];
  const b = BENCH[item?.market ?? 'US'];
  return (
    <main className="page">
      <Proto />
      <Back href="/trend" label="트렌드" />
      <div style={{ padding: '0 16px' }}>
        <div className="sub">{code} · {item ? `${item.market === 'KR' ? '한국' : '미국'} · ${item.kind}` : '정보 없음'}</div>
        <h1 style={{ margin: '2px 0 0', fontSize: 22 }}>{item?.name ?? code}</h1>
        <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
          <span className={`tag ${tone(r[1]) === 'up' ? 'up' : 'down'}`}>{(r[1] ?? 0) >= 0 ? '추세 위' : '추세 아래'}</span>
          <span className="tag">S&amp;P 대비 강도 상위 12% (예시)</span>
        </div>
      </div>
      <section className="card">
        <h2>기간 수익률</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '72px repeat(3,minmax(0,1fr))', rowGap: 8, fontSize: 13, textAlign: 'right', marginTop: 8 }}>
          <span /><span className="sub">1개월</span><span className="sub">3개월</span><span className="sub">6개월</span>
          <span style={{ textAlign: 'left' }}>이 종목</span>{r.map((v, i) => <span key={i} className={tone(v)}>{pct(v)}</span>)}
          <span style={{ textAlign: 'left' }}>기준</span>{b.map((v, i) => <span key={i}>{pct(v)}</span>)}
          <span style={{ textAlign: 'left' }} className="b">차이</span>{r.map((v, i) => <span key={i} className={`b ${tone(v == null ? null : v - b[i])}`}>{pp(v == null ? null : v - b[i])}</span>)}
        </div>
      </section>
      <section className="card" style={{ fontSize: 13 }}>
        <h2>위험·통계</h2>
        <div className="grid2" style={{ marginTop: 8 }}>
          <div><div className="sub">변동성(연)</div><div className="b" style={{ fontSize: 17 }}>—</div><div className="muted">데이터 연결 후 계산</div></div>
          <div><div className="sub">최대 낙폭</div><div className="b" style={{ fontSize: 17 }}>—</div><div className="muted">데이터 연결 후 계산</div></div>
        </div>
      </section>
      <section className="card" style={{ fontSize: 13 }}>
        <h2>재무</h2>
        <div className="sub" style={{ marginTop: 4 }}>— 재무 수집기(SEC EDGAR·OpenDART) 연결 후 표시. 공시일 기준.</div>
      </section>
      <div style={{ margin: '12px 16px 0' }}><Link href="/terms" className="sub">용어 풀이 보기 ›</Link></div>
    </main>
  );
}
