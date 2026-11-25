import Link from 'next/link';
import { tone, type Num } from '../lib/format';

export function Proto({ sample = true }: { sample?: boolean }) {
  return sample ? <div className="proto">프로토타입 · 모든 숫자는 예시 값</div> : null;
}

export function TabBar({ on }: { on: 'market' | 'invest' }) {
  return (
    <nav className="tabbar" aria-label="주요 탭">
      <div>
        <Link href="/" className={on === 'market' ? 'on' : ''}>시장</Link>
        <Link href="/invest" className={on === 'invest' ? 'on' : ''}>투자</Link>
      </div>
    </nav>
  );
}

export function MarketSeg({ on }: { on: 'today' | 'trend' }) {
  return (
    <div className="seg">
      <Link href="/" className={on === 'today' ? 'on' : ''}>오늘</Link>
      <Link href="/trend" className={on === 'trend' ? 'on' : ''}>트렌드</Link>
    </div>
  );
}

export function Signed({ v, text, className = '' }: { v: Num; text: string; className?: string }) {
  return <span className={`${tone(v)} ${className}`}>{text}</span>;
}

export function Back({ href, label }: { href: string; label: string }) {
  return <Link href={href} className="back">‹ {label}</Link>;
}
