import Link from 'next/link';
import { Connecting, TabBar, MarketSeg, Signed } from '../components/ui';
import { getMarket } from '../lib/source';
import { num, pct, moveLabel } from '../lib/format';
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
          <div className="sub">오늘 3줄 · AI가 데이터·뉴스로 작성</div>
          <p style={{ margin: '6px 0 0', fontSize: 15, lineHeight: 1.6 }}><b>무슨 일</b> · {AI.today.what}</p>
          <p style={{ margin: '6px 0 0', fontSize: 15, lineHeight: 1.6 }}><b>왜</b> · {AI.today.why}
            {AI.today.why_news[0] && <> <Link href={`/news/${AI.today.why_news[0]}`} style={{ color: '#9CC3FF' }}>근거 기사 ›</Link></>}</p>
          {AI.today.next.map((x) => (
            <p key={x.what} style={{ margin: '6px 0 0', fontSize: 15, lineHeight: 1.6 }}><b>다음에 볼 것</b> · {x.what} → {x.why}</p>
          ))}
        </section>
      ) : (
        <section className="card dark">
          <div className="sub">오늘 한 줄</div>
          <p style={{ margin: '4px 0 0', fontSize: 17, fontWeight: 700, lineHeight: 1.5 }}>{SUMMARY}</p>
          <div className="sub" style={{ marginTop: 6 }}>AI 3줄 요약은 매일 수집 뒤 채워져요</div>
        </section>
      )}
      {SIG && SIG.items.length ? (
        <section className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="dot" style={{ borderRadius: 5, background: LIGHT[SIG.state ?? 'none'][0] }} />
              <span className="b" style={{ fontSize: 15 }}>시장 신호등: {LIGHT[SIG.state ?? 'none'][1]}</span>
            </div>
            <span className="sub">3개 중 {SIG.good}개 좋음</span>
          </div>
          {SIG.items.map((s) => (
            <div key={s.key} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginTop: 10 }}>
              <span className="dot" style={{ borderRadius: 5, marginTop: 5, flex: 'none', background: s.good === null ? 'var(--edge)' : s.good ? 'var(--ok)' : 'var(--up)' }} />
              <div><div className="b" style={{ fontSize: 14 }}>{s.title} · {s.good === null ? '판단 못 함' : s.good ? '좋음' : '나쁨'}</div><div className="sub" style={{ lineHeight: 1.45 }}>{s.text}</div></div>
            </div>
          ))}
          <div className="sub" style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--line)' }}>3개 다 좋으면 초록, 2개 노랑, 1개 이하 빨강 · 지금 상태 표시예요(매매 신호 아님)</div>
        </section>
      ) : (
        <section className="card">
          <div className="b" style={{ fontSize: 15 }}>시장 추세 신호등: {TREND_LIGHT.state === null ? '—' : green ? '초록' : '빨강'}</div>
          <div className="sub">S&amp;P 500이 200일 평균선보다 {pct(TREND_LIGHT.gapPct)} · {BREADTH.total}개 업종 중 {BREADTH.above}개가 장기 추세 위</div>
        </section>
      )}
      <section className="card" style={{ paddingTop: 2, paddingBottom: 2 }}>
        <div className="muted" style={{ paddingTop: 10 }}>오늘 변화 옆 표시: 평소 하루 움직임과 비교</div>
        {QUOTES.map((q) => {
          const label = moveLabel(q.change, q.dailyStd);
          const warn = (q.id === 'vix' && (q.value ?? 0) >= 20) || (q.id === 'vkospi' && (q.value ?? 0) >= 25);
          return (
            <Link key={q.id} href={`/indicator/${q.id}`} className="row" style={{ display: 'block' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 15 }}>{q.name}</span>
                <span className="b" style={{ fontSize: 15 }}>{num(q.value, q.id === 'vix' ? 1 : 0)}{q.unit ?? ''}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                <span className="sub">{q.note ?? `한 달 ${pct(q.m1)} · 1년 ${pct(q.y1, 0)}`}</span>
                <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Signed v={q.change} text={q.changeText ?? pct(q.change)} />
                  <span className={`tag ${warn ? 'warn' : ''}`}>{warn ? '조금 불안' : label}</span>
                </span>
              </div>
            </Link>
          );
        })}
      </section>
      {AI.market && (
        <section className="card">
          <h2>그래서 시장은 · AI 해석</h2>
          <div style={{ marginTop: 10 }}><div className="b" style={{ fontSize: 13 }}>미국</div><p style={{ fontSize: 14, lineHeight: 1.6, margin: '3px 0 0' }}>{AI.market.us}</p></div>
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--line)' }}><div className="b" style={{ fontSize: 13 }}>한국</div><p style={{ fontSize: 14, lineHeight: 1.6, margin: '3px 0 0' }}>{AI.market.kr}</p></div>
          <div className="sub" style={{ marginTop: 10 }}>근거: 위 지표·신호등·오늘 뉴스 · {AI.generatedAt?.slice(0, 16).replace('T', ' ')} 작성</div>
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
