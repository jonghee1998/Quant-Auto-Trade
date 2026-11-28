'use client';
import { useState, type PointerEvent } from 'react';
import { num, pct, tone } from '../lib/format';
import { SPARK_PAD, SPARK_W, nearestIndex, shortDate, sparkPoints } from '../lib/spark';

/** 1년 주간 선 차트. 시작보다 위면 빨강(한국식 상승색), 아래면 파랑. 누르거나 올리면 그 날짜와 값을 보여 준다(폰에서는 손을 떼도 남는다). */
export default function Spark({ points, height = 120, digits = 2, unit = '' }: { points: [string, number | null][]; height?: number; digits?: number; unit?: string }) {
  const [sel, setSel] = useState<number | null>(null);
  const pts = sparkPoints(points);
  if (pts.length < 2) return null;
  const vals = pts.map((p) => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const W = SPARK_W, H = height, pad = SPARK_PAD;
  const x = (i: number) => pad + (i / (pts.length - 1)) * (W - pad * 2);
  const y = (v: number) => (hi === lo ? H / 2 : pad + (1 - (v - lo) / (hi - lo)) * (H - pad * 2));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' ');
  const last = pts.length - 1;
  const up = vals[last] >= vals[0];
  const color = up ? 'var(--up)' : 'var(--down)';
  const i = sel ?? last;
  const fromStart = vals[0] ? (vals[i] / vals[0] - 1) * 100 : null;
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    if (r.width > 0) setSel(nearestIndex((e.clientX - r.left) / r.width, pts.length));
  };
  return (
    <figure style={{ margin: '8px 0 0' }}>
      <div className="sparkread" aria-live="polite">
        <span className="sub">{sel == null ? '최근' : ''} {shortDate(pts[i][0])}</span>
        <span className="b">{num(vals[i], digits)}{unit}</span>
        <span className={`sub ${tone(fromStart)}`}>시작 대비 {pct(fromStart)}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img" className="spark"
        aria-label={`1년 흐름: ${pts[0][0]} ${vals[0]} → ${pts[last][0]} ${vals[last]}`}
        onPointerDown={move} onPointerMove={move} onPointerLeave={(e) => { if (e.pointerType === 'mouse') setSel(null); }}>
        <line x1={pad} x2={W - pad} y1={y(vals[0])} y2={y(vals[0])} stroke="var(--edge)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
        <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        {sel != null && <line x1={x(i)} x2={x(i)} y1={0} y2={H} stroke="var(--ink)" strokeWidth={1} opacity={0.35} vectorEffect="non-scaling-stroke" />}
      </svg>
      {/* 점은 SVG 밖에 그린다(가로로 늘린 SVG 안에서는 원이 찌그러진다) */}
      <div style={{ position: 'relative', height: 0 }}>
        <span className="sparkdot" style={{ left: `${(x(i) / W) * 100}%`, top: y(vals[i]) - H, background: color }} />
      </div>
      <figcaption className="sub" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>{shortDate(pts[0][0])}</span><span>점선 = 1년 전 값 · 눌러서 날짜별 값 보기</span><span>{shortDate(pts[last][0])}</span>
      </figcaption>
    </figure>
  );
}
