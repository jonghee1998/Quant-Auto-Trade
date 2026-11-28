// 같은 값을 잠깐 기억해 두는 작은 캐시(서버 메모리). 화면 이동마다 DB를 다시 읽지 않게 한다.
// 값만 담는다(진행 중인 요청은 담지 않는다 — Workers는 요청끼리 약속(promise)을 나눠 쓰면 안 된다).
type Entry = { at: number; value: unknown };
const store = new Map<string, Entry>();
const MAX = 200;

/** ttlMs 안에 읽은 값이 있으면 그대로, 없으면 load()로 읽는다. keep(value)가 false면(실패·빈 값) 기억하지 않는다. */
export async function memo<T>(key: string, ttlMs: number, load: () => Promise<T>, keep: (v: T) => boolean = () => true, now: () => number = Date.now): Promise<T> {
  const hit = store.get(key);
  if (hit && now() - hit.at < ttlMs) return hit.value as T;
  const value = await load();
  if (keep(value)) {
    if (store.size >= MAX && !store.has(key)) store.delete(store.keys().next().value as string); // 가장 오래된 것부터 버림
    store.delete(key); store.set(key, { at: now(), value });
  }
  return value;
}

export function memoClear(): void { store.clear(); }
