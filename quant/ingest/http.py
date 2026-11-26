"""주입 가능한 HTTP GET. 키는 호출하는 쪽(환경변수)에서만 넘기고 로그에 남기지 않는다."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


@dataclass(frozen=True)
class Response:
    status: int
    text: str

    def json(self) -> Any:
        return json.loads(self.text)


class Fetch(Protocol):
    def __call__(self, url: str, params: Mapping[str, Any] | None = None,
                 headers: Mapping[str, str] | None = None) -> Response: ...


class HttpError(RuntimeError):
    """URL·파라미터(키 포함)는 메시지에 넣지 않는다."""


NETWORK_ERROR = 0  # 연결 실패·시간 초과: 상태 코드 대신 0, 원래 예외(주소·키 포함)는 버린다


def requests_fetch(timeout: float = 30.0) -> Fetch:
    import requests

    def fetch(url, params=None, headers=None):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            # requests 예외 메시지에는 쿼리(키 포함)가 든 URL이 들어간다 → 종류만 남긴다
            return Response(NETWORK_ERROR, type(e).__name__)
        return Response(r.status_code, r.text)
    return fetch


def redact(text: str, secrets) -> str:
    """비밀값(원문·URL 인코딩 형태)을 ***로 가린다. 로그·DB에 남기기 전 마지막 방어선."""
    from urllib.parse import quote, quote_plus
    out = str(text)
    for v in secrets:
        if v and len(v) >= 8:
            for form in {v, quote(v, safe=""), quote_plus(v)}:
                out = out.replace(form, "***")
    return out


def get_json(fetch: Fetch, url: str, params=None, headers=None, *, source: str,
             retries: int = 2, sleep: Callable[[float], None] = time.sleep) -> Any:
    """429·5xx는 잠깐 쉬고 재시도, 그 외 실패는 HttpError."""
    for attempt in range(retries + 1):
        r = fetch(url, params, headers)
        if r.status == 200:
            return r.json()
        if (r.status in (NETWORK_ERROR, 429) or r.status >= 500) and attempt < retries:
            sleep(2.0 * (attempt + 1))
            continue
        if r.status == NETWORK_ERROR:
            raise HttpError(f"{source}: 연결 실패({r.text[:40]})")
        # 원인 파악용 응답 앞부분(키가 섞일 수 있어 호출한 쪽에서 redact 후 기록)
        snippet = " ".join(str(r.text or "").split())[:160]
        raise HttpError(f"{source}: HTTP {r.status}" + (f" · {snippet}" if snippet else ""))
    raise HttpError(f"{source}: 재시도 초과")  # pragma: no cover
