import Link from 'next/link';
import { tone, type Num } from '../lib/format';

/** 아직 만들지 않은 영역. 가짜 숫자 대신 무엇이 들어올지만 적는다. */
export function Planned({ title, note }: { title: string; note: string }) {
  return (
    <section className="card planned">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>{title}</h2><span className="tag">개발 예정</span>
      </div>
      <div className="sub" style={{ marginTop: 4, lineHeight: 1.5 }}>{note}</div>
    </section>
  );
}

/** 데이터를 못 읽었을 때. */
export function Connecting({ reason }: { reason?: string }) {
  return (
    <section className="card planned">
      <h2>데이터 연결 중</h2>
      <div className="sub" style={{ marginTop: 4 }}>{reason ? `${reason}. ` : ''}매일 14:37(한국시간) 수집 뒤 채워져요</div>
    </section>
  );
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
