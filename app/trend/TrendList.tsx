'use client';
import { useState } from 'react';
import Link from 'next/link';
import type { Item, Bench, Coverage, AiWhy } from '../../lib/types';
import { rankItems, barSpan, type Market, type Kind } from '../../lib/trend';
import { pct, tone } from '../../lib/format';

const PERIODS = ['1개월', '3개월', '6개월'] as const;
const MARKETS: [Market, string][] = [['US', '미국'], ['KR', '한국'], ['W', '나라별']];

export default function TrendList({ universe: UNIVERSE, bench: BENCH, coverage = {}, why = {} }: { universe: Item[]; bench: Bench; coverage?: Coverage; why?: Record<string, AiWhy> }) {
  const [strong, setStrong] = useState(true);
  const [market, setMarket] = useState<Market>('US');
  const [kind, setKind] = useState<Kind>('업종');
  const [period, setPeriod] = useState<0 | 1 | 2>(1);
  const rows = rankItems(UNIVERSE, market, kind, period, strong, 15);
  const cov = coverage[market === 'W' ? 'W/나라' : `${market}/${kind}`];
  const bench = BENCH[market][period];
  const all = rankItems(UNIVERSE, market, kind, period, true, 1000).map((i) => Math.abs(i.ret));
  const maxAbs = Math.max(1, ...all, Math.abs(bench ?? 0));
  const benchPos = barSpan(bench ?? 0, maxAbs);
  const benchLeft = (bench ?? 0) >= 0 ? benchPos.left + benchPos.width : benchPos.left;
  const what = market === 'W' ? '나라별' : `${market === 'US' ? '미국' : '한국'} ${kind === '업종' ? '업종 ETF' : '주식'}`;
  return (
    <>
      <div className="filters">
        <div className="seg in" role="group" aria-label="시장">
          {MARKETS.map(([m, l]) => <button key={m} type="button" className={market === m ? 'on' : ''} aria-pressed={market === m} onClick={() => setMarket(m)}>{l}</button>)}
        </div>
        <div className="pair">
          {market !== 'W' && (
            <div className="seg in sm" style={{ flex: 1 }} role="group" aria-label="종류">
              {(['업종', '주식'] as Kind[]).map((k) => <button key={k} type="button" className={kind === k ? 'on' : ''} aria-pressed={kind === k} onClick={() => setKind(k)}>{k === '업종' ? '업종·ETF' : '주식'}</button>)}
            </div>
          )}
          <div className="seg in sm" style={{ flex: 1.3 }} role="group" aria-label="기간">
            {PERIODS.map((l, i) => <button key={l} type="button" className={period === i ? 'on' : ''} aria-pressed={period === i} onClick={() => setPeriod(i as 0 | 1 | 2)}>{l}</button>)}
          </div>
        </div>
      </div>
      <div style={{ margin: '18px 16px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, letterSpacing: '-0.01em' }}>{what} TOP 15</h2>
        <div className="seg fit sm" role="group" aria-label="정렬">
          <button type="button" className={strong ? 'on' : ''} aria-pressed={strong} onClick={() => setStrong(true)}>상승</button>
          <button type="button" className={!strong ? 'on' : ''} aria-pressed={!strong} onClick={() => setStrong(false)}>하락</button>
        </div>
      </div>
      {cov && (
        <div className="sub" style={{ margin: '4px 16px 0', lineHeight: 1.5 }}>
          {cov.total ? `전체 ${cov.total.toLocaleString()}종목 중 ${cov.note ?? ''} ${cov.shown}종목을 비교` : `${cov.note ?? ''} ${cov.shown}개를 비교`}
        </div>
      )}
      <section className="card" style={{ paddingTop: 0, paddingBottom: 0 }}>
        {rows.length === 0 && <div className="row sub">아직 데이터가 없어요</div>}
                {rows.map((r, i) => {
          const s = barSpan(r.ret, maxAbs);
          const t = tone(r.ret);
          return (
            <Link key={r.code} href={`/stock/${r.code}?m=${r.market}`} className="row" style={{ flexWrap: 'wrap' }}>
              <span className="muted" style={{ width: 16 }}>{i + 1}</span>
              <div style={{ width: 96, flex: 'none' }}><div style={{ fontSize: 14 }}>{r.name}</div><div className="muted">{r.code}</div></div>
              <div className="bar">
                <div style={{ position: 'absolute', top: 0, height: 8, borderRadius: 4, left: `${s.left}%`, width: `${s.width}%`, background: t === 'up' ? 'var(--up)' : 'var(--down)' }} />
                <div style={{ position: 'absolute', top: -4, left: `${benchLeft}%`, width: 2, height: 16, background: 'var(--ink)' }} />
              </div>
              <span className={`${t} b`} style={{ width: 58, textAlign: 'right', fontSize: 14 }}>{pct(r.ret)}</span>
              {why[`${r.market}:${r.code}`] && <div className="sub" style={{ width: '100%', paddingLeft: 26, lineHeight: 1.45 }}>{why[`${r.market}:${r.code}`].line}</div>}
            </Link>
          );
        })}
      </section>
      <div className="sub" style={{ margin: '8px 16px 0' }}>세로선은 {market === 'KR' ? '코스피' : 'S&P 500'}({pct(bench)}). 오른쪽이면 시장보다 잘한 거예요.</div>
    </>
  );
}
