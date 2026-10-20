"""GitHub Actions helpers: annotations (shown on the run page and next to the file) and the step summary."""

from __future__ import annotations

import os


def in_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_prop(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def annotate(
    level: str, message: str, *, file: str | None = None, line: int | None = None, title: str | None = None
) -> None:
    """Print a ``::error``/``::warning``/``::notice`` command; a no-op outside GitHub Actions."""
    if not in_actions():
        return
    props = []
    if file:
        props.append(f"file={_escape_prop(file)}")
    if line:
        props.append(f"line={line}")
    if title:
        props.append(f"title={_escape_prop(title)}")
    head = f"::{level} {','.join(props)}" if props else f"::{level}"
    print(f"{head}::{_escape_data(message)}", flush=True)


def step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown.rstrip() + "\n")
