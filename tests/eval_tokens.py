"""Token-count evaluation harness — answers "which filter mode is cheaper".

For each fixture it counts tokens of the raw output and of each filter mode, then
applies the expected-cost model for the ``test`` workflow.

Run:  uv run python -m tests.eval_tokens
      uv run python -m tests.eval_tokens --p-fail 0.25

Token counts use Anthropic's token counter when an API key is available
(ANTHROPIC_API_KEY), else fall back to a rough char/4 proxy (flagged in output).
Char counts are only a proxy — trust the API counts for real decisions.
"""

import argparse
import os

from mcp_sbt_shell.output import clean_output

from . import fixtures

_MODEL = "claude-opus-4-8"


def _make_counter():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return (lambda text: max(1, len(text) // 4)), "char/4 proxy (no ANTHROPIC_API_KEY)"
    try:
        import anthropic
    except ImportError:
        return (lambda text: max(1, len(text) // 4)), "char/4 proxy (anthropic not installed)"

    client = anthropic.Anthropic(api_key=key)

    def count(text: str) -> int:
        resp = client.messages.count_tokens(
            model=_MODEL,
            messages=[{"role": "user", "content": text or " "}],
        )
        return resp.input_tokens

    return count, f"Anthropic token counter ({_MODEL})"


def _modes(name: str) -> dict[str, str]:
    cmd = fixtures.COMMANDS[name]
    raw = fixtures.ALL[name]
    return {
        "raw": raw,
        "safe": clean_output(
            raw, command=cmd, aggressive=False, collapse_success_enabled=False, keep_frame_prefixes=()
        ),
        "aggressive": clean_output(
            raw, command=cmd, aggressive=True, collapse_success_enabled=False, keep_frame_prefixes=()
        ),
        "collapse": clean_output(
            raw, command=cmd, aggressive=True, collapse_success_enabled=True, keep_frame_prefixes=()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--p-fail",
        type=float,
        default=0.2,
        help="fraction of `test` runs that fail (for the expected-cost model)",
    )
    args = parser.parse_args()

    count, source = _make_counter()
    print(f"Token source: {source}\n")

    header = f"{'fixture':<14} {'raw':>7} {'safe':>7} {'aggressive':>11} {'collapse':>9}"
    print(header)
    print("-" * len(header))
    counts: dict[str, dict[str, int]] = {}
    for name in fixtures.ALL:
        modes = _modes(name)
        c = {mode: count(text) for mode, text in modes.items()}
        counts[name] = c

        def pct(mode: str, c: dict[str, int] = c) -> str:
            return f"{c[mode]} ({100 * (c['raw'] - c[mode]) // max(1, c['raw'])}%)"

        print(f"{name:<14} {c['raw']:>7} {pct('safe'):>7} {pct('aggressive'):>11} {pct('collapse'):>9}")

    # Expected-cost model for the `test` workflow.
    # A (safe/inline): full every run.  B (aggressive + re-run raw on failure).
    green, red = counts["test-green"], counts["test-red"]
    p = args.p_fail
    full_pass, full_fail = green["safe"], red["safe"]
    agg_pass, agg_fail = green["aggressive"], red["aggressive"]

    cost_a = (1 - p) * full_pass + p * full_fail
    # With the ScalaTest-aware filter, aggressive keeps failure detail inline, so
    # no re-run is needed. (If detail were lost, add p * full_fail here.)
    cost_b = (1 - p) * agg_pass + p * agg_fail

    print(f"\nExpected `test` cost per run (p_fail={p}):")
    print(f"  A  safe/inline           : {cost_a:8.1f} tokens")
    print(f"  B  aggressive (detail inline): {cost_b:8.1f} tokens")
    if cost_a:
        print(f"  B saves {100 * (cost_a - cost_b) / cost_a:.1f}% vs A")


if __name__ == "__main__":
    main()
