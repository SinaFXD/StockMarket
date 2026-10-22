"""Shared test helpers. Tests never touch the network: every source is replaced by a fake."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def not_in_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the tests run inside a workflow, keep them out of that run's summary and annotations."""
    for name in (
        "GITHUB_ACTIONS",
        "GITHUB_STEP_SUMMARY",
        "GITHUB_RUN_ID",
        "GITHUB_REPOSITORY",
        "GITHUB_SHA",
        "GITHUB_EVENT_NAME",
        "GITHUB_SERVER_URL",
        "SEC_USER_AGENT",  # without it the screener never calls SEC EDGAR from a test
    ):
        monkeypatch.delenv(name, raising=False)


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.headers = headers or {}
        self.reason = "reason"

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakeSession:
    """Returns the queued responses in order (the last one repeats); records every call."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(
        self, url: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> FakeResponse:
        self.calls.append((url, params))
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return item


def write_csv(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path
