/** 화면을 누르면 데이터가 오기 전에 바로 뜨는 뼈대. */
export default function Loading() {
  return (
    <main className="page" aria-busy="true" aria-label="불러오는 중">
      <div style={{ padding: '0 16px' }}>
        <div className="skel" style={{ width: 96, height: 14 }} />
        <div className="skel" style={{ width: 180, height: 26, marginTop: 10 }} />
      </div>
      {[150, 110, 190].map((h) => (
        <section key={h} className="card">
          <div className="skel" style={{ width: 120, height: 14 }} />
          <div className="skel" style={{ height: h - 40, marginTop: 14 }} />
        </section>
      ))}
    </main>
  );
}
