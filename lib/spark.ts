// 선 차트 좌표 계산(화면과 테스트가 같이 쓴다).
export type SparkPoint = [string, number];
export const SPARK_W = 320;
export const SPARK_PAD = 6;

export function sparkPoints(points: [string, number | null][]): SparkPoint[] {
  return points.filter((p): p is SparkPoint => typeof p[1] === 'number' && Number.isFinite(p[1]));
}

/** 손가락·마우스의 가로 위치(차트 왼쪽 끝 0 ~ 오른쪽 끝 1)에서 가장 가까운 점 번호. */
export function nearestIndex(ratio: number, n: number): number {
  if (n <= 1 || !Number.isFinite(ratio)) return 0;
  const inner = (ratio * SPARK_W - SPARK_PAD) / (SPARK_W - SPARK_PAD * 2);
  return Math.min(n - 1, Math.max(0, Math.round(inner * (n - 1))));
}

/** '2026-03-06' → '26.03.06' */
export const shortDate = (d: string) => d.slice(2).replace(/-/g, '.');
