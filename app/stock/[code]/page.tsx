import Link from 'next/link';
import { Back, Connecting, Planned } from '../../../components/ui';
import { getMarket } from '../../../lib/source';
import { pct, pp, tone } from '../../../lib/format';

export const dynamic = 'force-dynamic';

export default async function Stock({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const d = await getMarket();
  const item = d.universe.find((i) => i.code === code);
  const r = item?.r ?? [null, null, null];
  const b = d.bench[item?.market ?? 'US'];
  return (
    <main className="page">
      <Back href="/trend" label="트렌드" />
      <div style={{ padding: '0 16px' }}>
        <div className="sub">{code} · {item ? `${item.market === 'KR' ? '한국' : '미국'} · ${item.kind}` : '정보 없음'}</div>
        <h1 style={{ margin: '2px 0 0', fontSize: 22 }}>{item?.name ?? code}</h1>
      </div>
      {d.sample || !item ? <Connecting reason={d.sample ? d.sampleReason : '이 종목은 아직 수집 대상이 아니에요'} /> : <section className="card">
        <h2>기간 수익률</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '72px repeat(3,minmax(0,1fr))', rowGap: 8, fontSize: 13, textAlign: 'right', marginTop: 8 }}>
          <span /><span className="sub">1개월</span><span className="sub">3개월</span><span className="sub">6개월</span>
          <span style={{ textAlign: 'left' }}>이 종목</span>{r.map((v, i) => <span key={i} className={tone(v)}>{pct(v)}</span>)}
          <span style={{ textAlign: 'left' }}>기준</span>{b.map((v, i) => <span key={i}>{pct(v)}</span>)}
          <span style={{ textAlign: 'left' }} className="b">차이</span>{r.map((v, i) => { const bi = b[i]; const diff = v == null || bi == null ? null : v - bi; return <span key={i} className={`b ${tone(diff)}`}>{pp(diff)}</span>; })}
        </div>
      </section>}
      <Planned title="위험·통계" note="변동성 · 최대 낙폭 · 베타 · 52주 위치 · 장기 추세(200일선 위/아래)." />
      <Planned title="재무" note="매출·이익 성장, PER·PBR, 분기 매출 추이 — 공시일 기준(미국 SEC, 한국 OpenDART)." />
      <div style={{ margin: '12px 16px 0' }}><Link href="/terms" className="sub">용어 풀이 보기 ›</Link></div>
    </main>
  );
}
