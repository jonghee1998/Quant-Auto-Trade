import Link from 'next/link';
import { Back, Connecting, Planned, TermsLink } from '../../../components/ui';
import { getMarket } from '../../../lib/source';
import { getDetail } from '../../../lib/detail';
import Spark from '../../../components/Spark';
import Star from '../../../components/Star';
import { num, pct, pp, sentences, tone } from '../../../lib/format';

export const dynamic = 'force-dynamic';

export default async function Stock({ params, searchParams }: { params: Promise<{ code: string }>; searchParams: Promise<{ m?: string }> }) {
  const { code } = await params;
  const { m } = await searchParams;
  const d = await getMarket();
  const item = d.universe.find((i) => i.code === code && (!m || i.market === m)) ?? d.universe.find((i) => i.code === code);
  const why = item ? d.ai.why?.[`${item.market}:${item.code}`] : undefined;
  const [whyFirst, ...whyRest] = sentences(why?.text);
  const det = item ? await getDetail(`${item.market}:${item.code}`) : null;
  const st = det?.stats;
  const f = det?.fund;
  const KR = item?.market === 'KR';
  const r = item?.r ?? [null, null, null];
  const b = d.bench[item?.market ?? 'US'];
  return (
    <main className="page">
      <Back href="/trend" label="트렌드" />
      <div style={{ padding: '0 16px' }}>
        <div className="sub">{code} · {item ? `${item.market === 'KR' ? '한국' : item.market === 'W' ? '나라별' : '미국'} ${item.kind}` : '정보 없음'}</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: '2px 0 0', fontSize: 22 }}>{item?.name ?? code}</h1>
          {item && <Star id={`${item.market}:${item.code}`} />}
        </div>
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
      {why ? (
        <>
          <section className="card dark brief">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="sub">{(item?.r[0] ?? 0) >= 0 ? '왜 올랐나' : '왜 내렸나'}</span>
              <span className={`tag ${why.confidence === '높음' ? 'ok' : why.confidence === '낮음' ? 'warn' : ''}`}>AI 해석, 확신 {why.confidence}</span>
            </div>
            <p className="lead" style={{ marginTop: 8, fontSize: 18, fontWeight: 600, lineHeight: 1.45, letterSpacing: '-0.01em' }}>{whyFirst}</p>
            {whyRest.length > 0 && (
              <div className="read" style={{ marginTop: 8 }}><ul>{whyRest.map((x) => <li key={x}>{x}</li>)}</ul></div>
            )}
            {why.tags.length > 0 && <div className="chips" style={{ marginTop: 12 }}>{why.tags.map((t) => <span key={t} className="tag">{t}</span>)}</div>}
          </section>
          <section className="card">
            <h2>근거</h2>
            {why.evidence.map((e) => (
              <div key={e.label} className="row" style={{ fontSize: 14, alignItems: 'flex-start' }}>
                <span style={{ display: 'flex', gap: 8, alignItems: 'baseline', lineHeight: 1.5 }}><span className="tag" style={{ flex: 'none' }}>{e.type}</span><span>{e.label}</span></span>
                {e.url && <a href={e.url} target="_blank" rel="noopener noreferrer" className="sub" style={{ flex: 'none', textDecoration: 'underline' }}>출처</a>}
              </div>
            ))}
            <div className="sub" style={{ marginTop: 6 }}>AI 해석은 틀릴 수 있어요.</div>
          </section>
        </>
      ) : item && <div className="sub" style={{ margin: '12px 16px 0' }}>오늘은 AI 해석이 없어요. 트렌드 TOP 15 중 이유를 찾은 종목만 써요.</div>}
      {item && (st && st.days >= 20 ? (
        <section className="card">
          <h2>1년 흐름과 위험</h2>
          {det && <Spark points={det.chart} />}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: '10px 12px', marginTop: 12, fontSize: 13 }}>
            <Stat label="52주 위치" value={st.pos == null ? '—' : `${st.pos}%`} hint={`최저 ${num(st.low, 2)} ~ 최고 ${num(st.high, 2)} 사이(100% = 최고)`} />
            <Stat label="장기 추세" value={st.ma200 == null ? '—' : st.ma200 >= 0 ? '200일선 위' : '200일선 아래'} hint={st.ma200 == null ? '데이터 200일 미만' : `200일 평균보다 ${pct(st.ma200)}`} />
            <Stat label="최대 낙폭(1년)" value={st.mdd == null ? '—' : `${st.mdd}%`} hint="1년 고점에서 가장 많이 빠진 폭" />
            <Stat label="변동성(1년)" value={st.vol == null ? '—' : `연 ${st.vol}%`} hint="클수록 출렁임이 커요. S&P 500은 15~20%" />
            <Stat label="베타" value={st.beta == null ? '—' : String(st.beta)} hint={`${item.market === 'KR' ? '코스피' : 'S&P 500'}가 1% 움직일 때의 평균 움직임`} />
            <Stat label="데이터" value={`${st.days}거래일`} hint={`${det?.date ?? ''} 기준`} />
          </div>
        </section>
      ) : <Connecting reason="1년 흐름·위험은 다음 수집 뒤 채워져요" />)}
      {item && item.kind === '주식' && item.market !== 'W' ? (f && f.quarters.length ? (
        <section className="card">
          <h2>재무 <span className="sub" style={{ fontWeight: 400 }}>{item.market === 'KR' ? '전자공시(OpenDART)' : '미국 SEC 공시'}, {f.filed} 접수분까지</span></h2>
          {(f.per != null || f.pbr != null) && (
            <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 13 }}>
            <span>PER <b>{f.per ?? '—'}</b>{f.perBasis ? <span className="sub"> ({f.perBasis})</span> : null}</span>
            <span>PBR <b>{f.pbr ?? '—'}</b></span>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 0.8fr', rowGap: 6, fontSize: 13, textAlign: 'right', marginTop: 10 }}>
            <span className="sub" style={{ textAlign: 'left' }}>분기 끝</span><span className="sub">매출</span><span className="sub">{KR ? '영업이익' : '순이익'}</span><span className="sub">매출 1년 전 대비</span>
            {f.quarters.slice().reverse().map((q) => (
              <Quarter key={q.end} q={q} op={KR} />
            ))}
          </div>
          <div className="sub" style={{ marginTop: 8, lineHeight: 1.5 }}>{KR ? '단위 억 원, 연결 기준(없으면 개별). 4분기는 연간에서 3분기 누적을 뺀 값.' : '단위 억 달러.'} PER은 시가총액 ÷ 1년 이익, PBR은 시가총액 ÷ 순자산. 낮을수록 싸요.</div>
        </section>
      ) : <Connecting reason="재무는 다음 수집 뒤 채워져요" />) : item && (
        null
      )}
      <TermsLink />
    </main>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <div className="sub">{label}</div>
      <div className="b" style={{ fontSize: 16, marginTop: 2 }}>{value}</div>
      <div className="sub" style={{ lineHeight: 1.4, marginTop: 2 }}>{hint}</div>
    </div>
  );
}

const eok = (v: number | null) => (v == null ? '—' : (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 0 }));

function Quarter({ q, op }: { q: { end: string; revenue: number | null; netIncome: number | null; opIncome?: number | null; revYoY: number | null }; op: boolean }) {
  return (
    <>
      <span style={{ textAlign: 'left' }}>{q.end.slice(2, 7).replace('-', '.')}</span>
      <span>{eok(q.revenue)}</span>
      <span className={tone(op ? q.opIncome ?? null : q.netIncome)}>{eok(op ? q.opIncome ?? null : q.netIncome)}</span>
      <span className={tone(q.revYoY)}>{pct(q.revYoY)}</span>
    </>
  );
}
