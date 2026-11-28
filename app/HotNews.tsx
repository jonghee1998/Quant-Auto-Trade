'use client';
import { useState } from 'react';
import Link from 'next/link';
import type { AiNews } from '../lib/types';

const CATS = ['금리·연준', '미국 증시', '한국 증시', '기업·실적', '유가·환율', '기타'];

/** 핫한 뉴스: 카테고리 칩으로 거르기. 순서는 AI가 매긴 핫한 순(많이 보도 + 시장 영향). */
export default function HotNews({ news }: { news: AiNews[] }) {
  const [cat, setCat] = useState('전체');
  const cats = ['전체', ...CATS.filter((c) => news.some((n) => n.cat === c))];
  const shown = cat === '전체' ? news : news.filter((n) => n.cat === cat);
  const groups = cat === '전체' ? cats.slice(1).map((c) => [c, shown.filter((n) => n.cat === c)] as const) : [[cat, shown] as const];
  return (
    <section className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2>핫한 뉴스</h2><span className="sub">많이 보도된 순</span>
      </div>
      <div className="chips" style={{ marginTop: 10, flexWrap: 'nowrap', overflowX: 'auto' }}>
        {cats.map((c) => <button key={c} type="button" className={`chip ${cat === c ? 'on' : ''}`} style={{ flex: 'none' }} onClick={() => setCat(c)}>{c}</button>)}
      </div>
      {groups.map(([c, list]) => list.length === 0 ? null : (
        <div key={c}>
          {cat === '전체' && <div className="muted" style={{ marginTop: 12 }}>{c}</div>}
          {list.map((n) => (
            <Link key={n.id} href={`/news/${n.id}`} className="row" style={{ display: 'block' }}>
              <div style={{ fontSize: 14, lineHeight: 1.45 }}>{n.title}</div>
              <div className="sub" style={{ marginTop: 2 }}>{n.where}, {n.outlets}곳 보도</div>
            </Link>
          ))}
        </div>
      ))}
    </section>
  );
}
