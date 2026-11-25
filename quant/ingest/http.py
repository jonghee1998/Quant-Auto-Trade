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


def requests_fetch(timeout: float = 30.0) -> Fetch:
    import requests

    def fetch(url, params=None, headers=None):
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        return Response(r.status_code, r.text)
    return fetch


def get_json(fetch: Fetch, url: str, params=None, headers=None, *, source: str,
             retries: int = 2, sleep: Callable[[float], None] = time.sleep) -> Any:
    """429·5xx는 잠깐 쉬고 재시도, 그 외 실패는 HttpError."""
    for attempt in range(retries + 1):
        r = fetch(url, params, headers)
        if r.status == 200:
            return r.json()
        if (r.status == 429 or r.status >= 500) and attempt < retries:
            sleep(2.0 * (attempt + 1))
            continue
        raise HttpError(f"{source}: HTTP {r.status}")
    raise HttpError(f"{source}: 재시도 초과")  # pragma: no cover
