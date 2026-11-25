'use client';
import { useState } from 'react';
import Link from 'next/link';
import type { Item, Bench } from '../../lib/mock';
import { rankItems, barSpan, type Market, type Kind } from '../../lib/trend';
import { pct, tone } from '../../lib/format';

const PERIODS = ['1개월', '3개월', '6개월'] as const;
const MARKETS: [Market, string][] = [['US', '미국'], ['KR', '한국'], ['W', '나라별']];

export default function TrendList({ universe: UNIVERSE, bench: BENCH }: { universe: Item[]; bench: Bench }) {
  const [strong, setStrong] = useState(true);
  const [market, setMarket] = useState<Market>('US');
  const [kind, setKind] = useState<Kind>('업종');
  const [period, setPeriod] = useState<0 | 1 | 2>(1);
  const rows = rankItems(UNIVERSE, market, kind, period, strong);
  const bench = BENCH[market][period];
  const all = rankItems(UNIVERSE, market, kind, period, true, 1000).map((i) => Math.abs(i.ret));
  const maxAbs = Math.max(1, ...all, Math.abs(bench ?? 0));
  const benchPos = barSpan(bench ?? 0, maxAbs);
  const benchLeft = (bench ?? 0) >= 0 ? benchPos.left + benchPos.width : benchPos.left;
  const what = market === 'W' ? '나라별' : `${market === 'US' ? '미국' : '한국'} ${kind === '업종' ? '업종 ETF' : '주식'}`;
  return (
    <>
      <div className="seg">
        <button type="button" className={strong ? 'on' : ''} onClick={() => setStrong(true)}>강한 곳</button>
        <button type="button" className={!strong ? 'on' : ''} onClick={() => setStrong(false)}>약한 곳</button>
      </div>
      <div style={{ margin: '10px 16px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="chips"><span className="sub" style={{ width: 34 }}>어디</span>
          {MARKETS.map(([m, l]) => <button key={m} type="button" className={`chip ${market === m ? 'on' : ''}`} onClick={() => setMarket(m)}>{l}</button>)}
        </div>
        {market !== 'W' && (
          <div className="chips"><span className="sub" style={{ width: 34 }}>무엇</span>
            {(['업종', '주식'] as Kind[]).map((k) => <button key={k} type="button" className={`chip ${kind === k ? 'on' : ''}`} onClick={() => setKind(k)}>{k === '업종' ? '업종·ETF' : '주식'}</button>)}
          </div>
        )}
        <div className="chips"><span className="sub" style={{ width: 34 }}>기간</span>
          {PERIODS.map((l, i) => <button key={l} type="button" className={`chip ${period === i ? 'on' : ''}`} onClick={() => setPeriod(i as 0 | 1 | 2)}>{l}</button>)}
        </div>
      </div>
      <div style={{ margin: '16px 16px 0', fontSize: 16, fontWeight: 700 }}>{what} · 최근 {PERIODS[period]} {strong ? '가장 많이 오른 곳' : '가장 많이 내린 곳'}</div>
      <section className="card" style={{ paddingTop: 0, paddingBottom: 0 }}>
        {rows.length === 0 && <div className="row sub">— 아직 데이터가 없어요</div>}
                {rows.map((r, i) => {
          const s = barSpan(r.ret, maxAbs);
          const t = tone(r.ret);
          return (
            <Link key={r.code} href={`/stock/${r.code}`} className="row">
              <span className="muted" style={{ width: 16 }}>{i + 1}</span>
              <div style={{ width: 96, flex: 'none' }}><div style={{ fontSize: 14 }}>{r.name}</div><div className="muted">{r.code}</div></div>
              <div className="bar">
                <div style={{ position: 'absolute', top: 0, height: 8, borderRadius: 4, left: `${s.left}%`, width: `${s.width}%`, background: t === 'up' ? 'var(--up)' : 'var(--down)' }} />
                <div style={{ position: 'absolute', top: -4, left: `${benchLeft}%`, width: 2, height: 16, background: 'var(--ink)' }} />
              </div>
              <span className={`${t} b`} style={{ width: 58, textAlign: 'right', fontSize: 14 }}>{pct(r.ret)}</span>
            </Link>
          );
        })}
      </section>
      <div className="sub" style={{ margin: '8px 16px 0' }}>세로선 = {market === 'KR' ? '코스피' : 'S&P 500'} {pct(bench)}. 선 오른쪽이면 시장보다 잘함.</div>
    </>
  );
}
