'use client';
import { useEffect, useState } from 'react';
import { readWatch, toggleWatch, WATCH_EVENT } from '../lib/watch';

export default function Star({ id }: { id: string }) {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const sync = () => setOn(readWatch().includes(id));
    sync();
    window.addEventListener(WATCH_EVENT, sync);
    return () => window.removeEventListener(WATCH_EVENT, sync);
  }, [id]);
  return (
    <button type="button" onClick={() => setOn(toggleWatch(id).includes(id))} aria-pressed={on}
      aria-label={on ? '관심 종목에서 빼기' : '관심 종목에 담기'}
      style={{ minWidth: 44, height: 44, border: 'none', background: 'none', fontSize: 24, color: on ? '#D99A1E' : 'var(--edge)' }}>
      {on ? '★' : '☆'}
    </button>
  );
}
