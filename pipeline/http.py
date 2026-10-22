"""Shared HTTP client: polite throttling, retries with backoff, and secret redaction.

Error messages end up in ``site/data/health.json``, which is published, so every message that leaves
this module goes through :func:`redact` first.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable
from typing import Any

import requests

from .config import USER_AGENT

RETRY_STATUS = {429, 500, 502, 503, 504}
_SECRET_PARAM = re.compile(r"(api_key|apikey|token|key)=([^&\s\"']+)", re.IGNORECASE)
_SECRET_ENV_VARS = ("FRED_API_KEY",)
_TITLE = re.compile(r"<title[^>]*>(.*?)<", re.IGNORECASE | re.DOTALL)


class FetchError(Exception):
    """A source could not deliver usable data. The message is already redacted."""


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove API keys from text: known secret values and any ``api_key=...`` style query parameter."""
    values = [s for s in secrets if s] + [os.environ.get(v, "") for v in _SECRET_ENV_VARS]
    for value in values:
        if len(value) >= 6:
            text = text.replace(value, "***")
    return _SECRET_PARAM.sub(lambda m: f"{m.group(1)}=***", text)


class HttpClient:
    def __init__(
        self,
        *,
        min_interval: float = 0.0,
        retries: int = 3,
        backoff: float = 1.5,
        timeout: float = 45,
        user_agent: str = USER_AGENT,
        secrets: Iterable[str] = (),
        session: requests.Session | None = None,
        sleep=time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", user_agent)
        self.min_interval = min_interval
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.secrets = tuple(secrets)
        self._sleep = sleep
        self._last_request = 0.0
        self.requests_made = 0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()

    def _get(self, url: str, params: dict[str, Any] | None, parse: Callable[[requests.Response], Any]) -> Any:
        last_problem = "no attempt made"
        for attempt in range(self.retries + 1):
            if attempt:
                self._sleep(self.backoff * 2 ** (attempt - 1))
            self._throttle()
            self.requests_made += 1
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_problem = f"network error: {type(exc).__name__}: {exc}"
                continue
            if resp.status_code in RETRY_STATUS:
                last_problem = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    self._sleep(min(int(retry_after), 60))
                continue
            if resp.status_code >= 400:
                raise FetchError(redact(f"HTTP {resp.status_code}: {_error_text(resp)}", self.secrets))
            try:
                return parse(resp)
            except ValueError as exc:
                last_problem = f"{exc} (HTTP {resp.status_code})"
                continue
        raise FetchError(redact(f"gave up after {self.retries + 1} attempts: {last_problem}", self.secrets))

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        def parse(resp: requests.Response) -> Any:
            try:
                return resp.json()
            except ValueError:
                title = _html_title(resp.text)
                hint = f"; the source returned the web page '{title}'" if title else ""
                if title and "maintenance" in title.lower():
                    hint += " (the source is down for maintenance)"
                raise ValueError(f"response was not JSON{hint}") from None

        return self._get(url, params, parse)

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        def parse(resp: requests.Response) -> str:
            if _html_title(resp.text):
                raise ValueError(f"expected data but got the web page '{_html_title(resp.text)}'")
            return resp.text

        return self._get(url, params, parse)


def _html_title(text: str) -> str | None:
    m = _TITLE.search(text[:5000])
    return " ".join(m.group(1).split())[:120] if m else None


def _error_text(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200].strip() or resp.reason
    if isinstance(body, dict):
        for k in ("error_message", "message", "error"):
            if body.get(k):
                return str(body[k])
    return str(body)[:200]
