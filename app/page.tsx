import { Fragment } from 'react';
import Link from 'next/link';
import { Connecting, TabBar, MarketSeg, Signed } from '../components/ui';
import { getMarket } from '../lib/source';
import { num, pct, moveLabel, quoteDigits } from '../lib/format';
import HotNews from './HotNews';

export const dynamic = 'force-dynamic'; // 배포 때 만든 화면을 재사용하지 않고 요청마다 DB에서 읽는다

const LIGHT: Record<string, [string, string]> = {
  green: ['var(--ok)', '초록'], yellow: ['#D99A1E', '노랑 (주의)'], red: ['var(--up)', '빨강'], none: ['var(--edge)', '—'],
};

export default async function Today() {
  const d = await getMarket();
  const { asOf: AS_OF, quotes: QUOTES, summary: SUMMARY, trendLight: TREND_LIGHT, breadth: BREADTH, news: NEWS } = d;
  const green = TREND_LIGHT.state === 'green';
  const AI = d.ai;
  const SIG = d.signals;
  return (
    <main className="page">
      <div className="head">
        <h1>시장</h1>
        <Link href="/data" className="sub" style={{ display: 'flex', alignItems: 'center', gap: 6, height: 44 }}>
          <span className="dot" style={{ background: 'var(--ok)', borderRadius: 5 }} />{AS_OF} 기준
        </Link>
      </div>
      <MarketSeg on="today" />
      {d.sample ? <Connecting reason={d.sampleReason} /> : <>
      {AI.today ? (
        <section className="card dark">
          <div className="sub">오늘 3줄 요약, AI가 데이터와 뉴스로 작성</div>
          <dl className="kv" style={{ margin: '10px 0 0', fontSize: 15, lineHeight: 1.6 }}>
            <dt>무슨 일</dt><dd>{AI.today.what}</dd>
            <dt>왜</dt>
            <dd>{AI.today.why}
              {AI.today.why_news[0] && <> <Link href={`/news/${AI.today.why_news[0]}`} style={{ color: '#9CC3FF', whiteSpace: 'nowrap' }}>근거 기사 보기</Link></>}</dd>
            {AI.today.next.map((x) => (
              <Fragment key={x.what}><dt>다음</dt><dd>{x.what}. <span style={{ color: 'var(--dark-sub)' }}>{x.why}</span></dd></Fragment>
            ))}
          </dl>
        </section>
      ) : (
        <section className="card dark">
          <div className="sub">오늘 한 줄</div>
          <p style={{ margin: '4px 0 0', fontSize: 17, fontWeight: 600, lineHeight: 1.5 }}>{SUMMARY}</p>
          <div className="sub" style={{ marginTop: 6 }}>AI 3줄 요약은 매일 수집 뒤 채워져요</div>
        </section>
      )}
      {SIG && SIG.items.length ? (
        <section className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="dot" style={{ borderRadius: 5, background: LIGHT[SIG.state ?? 'none'][0] }} />
              시장 신호등 {LIGHT[SIG.state ?? 'none'][1]}
            </h2>
            <span className="sub">{SIG.items.length}개 중 {SIG.good}개 좋음</span>
          </div>
          <div style={{ marginTop: 6 }}>
            {SIG.items.map((s) => (
              <div key={s.key} className="row" style={{ alignItems: 'flex-start' }}>
                <div><div style={{ fontSize: 14, fontWeight: 500 }}>{s.title}</div><div className="sub" style={{ marginTop: 1 }}>{s.text}</div></div>
                <span className={`tag ${s.good === null ? '' : s.good ? 'ok' : 'up'}`} style={{ flex: 'none', marginTop: 2 }}>{s.good === null ? '판단 못 함' : s.good ? '좋음' : '나쁨'}</span>
              </div>
            ))}
          </div>
          <div className="muted" style={{ paddingTop: 8, borderTop: '1px solid var(--line)' }}>3개 다 좋으면 초록, 2개면 노랑, 1개 이하면 빨강이에요. 지금 상태를 보여줄 뿐 매매 신호가 아니에요.</div>
        </section>
      ) : (
        <section className="card">
          <h2>시장 추세 신호등 {TREND_LIGHT.state === null ? '—' : green ? '초록' : '빨강'}</h2>
          <div className="sub" style={{ marginTop: 4 }}>S&amp;P 500이 200일 평균선보다 {pct(TREND_LIGHT.gapPct)}, {BREADTH.total}개 업종 중 {BREADTH.above}개가 장기 추세 위</div>
        </section>
      )}
      <section className="card" style={{ paddingTop: 4, paddingBottom: 4 }}>
        {QUOTES.map((q) => {
          const big = moveLabel(q.change, q.dailyStd) === '큰 움직임';
          const warn = (q.id === 'vix' && (q.value ?? 0) >= 20) || (q.id === 'vkospi' && (q.value ?? 0) >= 25);
          return (
            <Link key={q.id} href={`/indicator/${q.id}`} className="quote">
              <span style={{ display: 'flex', gap: 6, alignItems: 'center', minWidth: 0 }}>
                <span style={{ fontSize: 15, fontWeight: 500 }}>{q.name}</span>
                {warn ? <span className="tag warn">조금 불안</span> : big && <span className="tag">평소보다 큰 움직임</span>}
              </span>
              <span className="v">{num(q.value, quoteDigits(q.id, q.unit))}{q.unit ?? ''}</span>
              <span className="sub">{q.note ?? `한 달 ${pct(q.m1)}, 1년 ${pct(q.y1, 0)}`}</span>
              <Signed v={q.change} text={q.changeText ?? pct(q.change)} className="c" />
            </Link>
          );
        })}
        <div className="muted" style={{ padding: '8px 0 10px', borderTop: '1px solid var(--line)' }}>오른쪽 아래는 오늘 변화예요. 평소 하루 움직임의 2배를 넘으면 표시해요.</div>
      </section>
      {AI.market && (
        <section className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}><h2>그래서 시장은</h2><span className="sub">AI 해석</span></div>
          <dl className="kv" style={{ margin: '10px 0 0', fontSize: 14, lineHeight: 1.6 }}>
            <dt>미국</dt><dd>{AI.market.us}</dd>
            <dt>한국</dt><dd>{AI.market.kr}</dd>
          </dl>
          <div className="muted" style={{ marginTop: 10 }}>위 지표, 신호등, 오늘 뉴스를 근거로 {AI.generatedAt?.slice(0, 16).replace('T', ' ')}에 작성</div>
        </section>
      )}
      {AI.news && AI.news.length ? <HotNews news={AI.news} /> : (
        <section className="card">
          <h2>오늘 뉴스</h2>
          {NEWS.map((n) => (
            <div key={n.title} className="row" style={{ fontSize: 14 }}>{n.title} <span className="sub">{n.where}</span></div>
          ))}
        </section>
      )}
      </>}
      <TabBar on="market" />
    </main>
  );
}
