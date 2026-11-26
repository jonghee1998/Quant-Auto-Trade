/** 1년 주간 선 차트(축 없음). 시작보다 위면 빨강(한국식 상승색), 아래면 파랑. 최고·최저 값만 표시. */
export default function Spark({ points, height = 120 }: { points: [string, number | null][]; height?: number }) {
  const pts = points.filter((p): p is [string, number] => typeof p[1] === 'number');
  if (pts.length < 2) return null;
  const vals = pts.map((p) => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const W = 320, H = height, pad = 6;
  const x = (i: number) => pad + (i / (pts.length - 1)) * (W - pad * 2);
  const y = (v: number) => (hi === lo ? H / 2 : pad + (1 - (v - lo) / (hi - lo)) * (H - pad * 2));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' ');
  const up = vals[vals.length - 1] >= vals[0];
  return (
    <figure style={{ margin: '8px 0 0' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`1년 흐름: ${pts[0][0]} ${vals[0]} → ${pts[pts.length - 1][0]} ${vals[vals.length - 1]}`}>
        <line x1={pad} x2={W - pad} y1={y(vals[0])} y2={y(vals[0])} stroke="var(--edge)" strokeDasharray="3 3" />
        <path d={d} fill="none" stroke={up ? 'var(--up)' : 'var(--down)'} strokeWidth={2} strokeLinejoin="round" />
      </svg>
      <figcaption className="sub" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>{pts[0][0].slice(2).replace(/-/g, '.')}</span><span>점선 = 1년 전 값</span><span>{pts[pts.length - 1][0].slice(2).replace(/-/g, '.')}</span>
      </figcaption>
    </figure>
  );
}
