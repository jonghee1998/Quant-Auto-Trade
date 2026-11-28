'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { AiWhy, Item } from '../../lib/types';
import { pct, tone } from '../../lib/format';
import { readWatch, WATCH_EVENT } from '../../lib/watch';

/** 트렌드 맨 위 관심 종목. 이 기기에 담아 둔 것(종목 상세의 ☆). */
export default function WatchList({ universe, why }: { universe: Item[]; why: Record<string, AiWhy> }) {
  const [ids, setIds] = useState<string[] | null>(null);
  useEffect(() => {
    const sync = () => setIds(readWatch());
    sync();
    window.addEventListener(WATCH_EVENT, sync);
    return () => window.removeEventListener(WATCH_EVENT, sync);
  }, []);
  const items = (ids ?? []).map((id) => universe.find((u) => `${u.market}:${u.code}` === id) ?? { id }).slice(0, 20);
  return (
    <section className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2>관심 종목</h2><span className="sub">1개월, 3개월</span>
      </div>
      {ids !== null && items.length === 0 && (
        <div className="sub" style={{ marginTop: 6, lineHeight: 1.5 }}>종목 화면에서 ☆를 누르면 여기에 떠요. 이 기기에만 저장돼요.</div>
      )}
      {items.map((u) => 'code' in u ? (
        <Link key={u.code + u.market} href={`/stock/${u.code}?m=${u.market}`} className="row" style={{ flexWrap: 'wrap' }}>
          <span style={{ flex: 1, minWidth: 0, fontSize: 14 }}>{u.name} <span className="sub">{u.code}</span></span>
          <span className={tone(u.r[0])} style={{ width: 58, textAlign: 'right', fontSize: 13 }}>{pct(u.r[0])}</span>
          <span className={`${tone(u.r[1])} b`} style={{ width: 58, textAlign: 'right', fontSize: 14 }}>{pct(u.r[1])}</span>
          {why[`${u.market}:${u.code}`] && <div className="sub" style={{ width: '100%', lineHeight: 1.45 }}>{why[`${u.market}:${u.code}`].line} ›</div>}
        </Link>
      ) : (
        <div key={u.id} className="row sub" style={{ fontSize: 13 }}>{u.id.split(':')[1]}은 오늘 목록에 없어요(거래대금 순위 밖)</div>
      ))}
    </section>
  );
}
