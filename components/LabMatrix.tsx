import { labTally, type Verdict } from '../lib/labRounds';

const CLS: Record<Verdict, string> = { 후보: 'cand', 보류: 'hold', 탈락: '' };

/** 실험 성적판: 실험 하나가 칸 하나(오래된 라운드부터). 색은 판정 — 초록 후보·호박색 보류·회색 탈락. */
export default function LabMatrix({ light = false }: { light?: boolean }) {
  const t = labTally();
  return (
    <div className={`mx ${light ? 'light' : ''}`} role="img" aria-label={`실험 ${t.total}개: 후보 ${t.count.후보}, 보류 ${t.count.보류}, 탈락 ${t.count.탈락}`}>
      {t.cells.map((v, i) => <i key={i} className={v === null ? 'gap' : CLS[v]} />)}
    </div>
  );
}
