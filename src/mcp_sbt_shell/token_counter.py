"""Optional runtime token-savings counter — a testing aid, off by default.

Enabled with ``--count-tokens``. For each ``sbt_execute`` call it counts the
tokens of the raw sbt output and of what is actually returned to the client, logs
the per-call saving to stderr, and accumulates a session total printed on
shutdown. Counts come from Anthropic's ``count_tokens`` API when
``ANTHROPIC_API_KEY`` is set (accurate), otherwise a rough ``char/4`` proxy.

This is intended for local testing, not the shared hot path: the Anthropic
counter makes a network call per command.
"""

import sys
from collections.abc import Callable

_MODEL = "claude-opus-4-8"

CountFn = Callable[[str], int]


def _proxy(text: str) -> int:
    return max(1, len(text) // 4)


def make_counter() -> tuple[CountFn, str]:
    """Return ``(count_fn, source_label)``; ``count_fn`` maps text -> token count."""
    import os

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("[token-count] ANTHROPIC_API_KEY not set — using char/4 proxy", file=sys.stderr)
        return _proxy, "char/4 proxy"
    try:
        import anthropic
    except ImportError:
        print("[token-count] anthropic not installed — using char/4 proxy", file=sys.stderr)
        return _proxy, "char/4 proxy"

    client = anthropic.Anthropic(api_key=key)

    def count(text: str) -> int:
        try:
            resp = client.messages.count_tokens(
                model=_MODEL,
                messages=[{"role": "user", "content": text or " "}],
            )
            return resp.input_tokens
        except Exception as e:
            print(f"[token-count] count_tokens failed ({e!s}) — char/4 proxy this call", file=sys.stderr)
            return _proxy(text)

    return count, f"Anthropic count_tokens ({_MODEL})"


class SavingsTracker:
    """Accumulates token savings across calls and logs them to stderr."""

    def __init__(self, count_fn: CountFn, source: str) -> None:
        self._count = count_fn
        self.source = source
        self.calls = 0
        self.raw_tokens = 0
        self.returned_tokens = 0

    @property
    def saved(self) -> int:
        return self.raw_tokens - self.returned_tokens

    def record(self, command: str, raw_output: str, returned_output: str) -> None:
        raw = self._count(raw_output)
        returned = self._count(returned_output)
        self.calls += 1
        self.raw_tokens += raw
        self.returned_tokens += returned
        saved = raw - returned
        pct = (100 * saved // raw) if raw else 0
        print(
            f"[token-count] {command!r}: {raw} -> {returned} tokens, saved {saved} ({pct}%)",
            file=sys.stderr,
        )

    def log_summary(self) -> None:
        if self.calls == 0:
            print("[token-count] no commands executed — nothing to report", file=sys.stderr)
            return
        pct = (100 * self.saved // self.raw_tokens) if self.raw_tokens else 0
        print(
            f"[token-count] session total ({self.source}): {self.calls} calls, "
            f"{self.raw_tokens} -> {self.returned_tokens} tokens, saved {self.saved} ({pct}%)",
            file=sys.stderr,
        )
