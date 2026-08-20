r"""A/B proof: this server vs. letting Claude spin up its own cold sbt shells.

The question is NOT "does filtering help" (that's ``eval_tokens.py``). It's the
end-to-end claim: for a realistic session, does routing sbt through the
persistent, output-filtering MCP server put fewer tokens into Claude's context
than the alternative — Claude running ``sbt "<cmd>"`` via Bash each time?

Two arms, scored on tokens that actually land in the model's context:

  Arm A (no server): each command is a cold ``sbt "<cmd>"`` Bash call. Claude
    sees the full raw stdout, INCLUDING the boot preamble, on EVERY call.

  Arm B (this server): sbt boots once, server-side — that output never reaches
    the model. Each command returns filtered output. Add a one-time cost for the
    ``sbt_execute`` tool schema that sits in the context.

Both arms are driven by REAL captures from the topaz-d worktree (quantity
module): a genuine 31-source compile and a green 226-test suite. See
``real_captures.py``.

Run:  uv run python -m tests.eval_savings
      ANTHROPIC_API_KEY=sk-ant-... uv run python -m tests.eval_savings   # real counts
      uv run python -m tests.eval_savings --compiles 6 --tests 3
"""

import argparse

from mcp_sbt_shell import server
from mcp_sbt_shell.output import clean_output
from mcp_sbt_shell.token_counter import make_counter

from . import real_captures

_CASES = ["compile", "test"]


def _prod_filter(raw: str, command: str) -> str:
    """The recommended production config: aggressive + collapse-success."""
    return clean_output(
        raw, command=command, aggressive=True, collapse_success_enabled=True, keep_frame_prefixes=()
    )


def _schema_overhead_text() -> str:
    """Approximate the fixed per-context cost of exposing the tool: its docstring
    dominates the JSON schema. Labelled approximate in the output."""
    doc = server.sbt_execute.__doc__ or ""
    return f"sbt_execute(command: string, raw: boolean) -> string\n{doc}"


def _pct(base: int, now: int) -> str:
    return f"{100 * (base - now) // max(1, base)}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiles", type=int, default=6, help="compile calls in the modelled session")
    parser.add_argument("--tests", type=int, default=3, help="test calls in the modelled session")
    args = parser.parse_args()

    count, source = make_counter()
    print(f"Token source: {source}")
    if "proxy" in source:
        print("(char/4 is a proxy — export ANTHROPIC_API_KEY for real counts)")
    print()

    # ---- Per-command breakdown: same command, both arms, all REAL captures ----
    per_call = {}  # case -> (a_cold, b_warm_raw, b_warm_filtered)
    print("PER-COMMAND (same command each row; Arm A cold+raw vs Arm B warm+filtered)")
    hdr = f"  {'command':<20} {'A cold raw':>11} {'B warm raw':>11} {'B filtered':>11} {'saved':>10}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for case in _CASES:
        cmd = real_captures.command(case)
        a_cold = count(real_captures.cold(case))
        raw = real_captures.warm(case)
        b_raw = count(raw)
        b_filt = count(_prod_filter(raw, cmd))
        per_call[case] = (a_cold, b_raw, b_filt)
        print(f"  {cmd:<20} {a_cold:>11} {b_raw:>11} {b_filt:>11} {_pct(a_cold, b_filt):>10}")

    # ---- Decompose one command so the parts SUM to the total ----
    a_cold, b_raw, b_filt = per_call["test"]
    persistent = a_cold - b_raw
    filtering = b_raw - b_filt
    boot = count(real_captures.boot_preamble())
    print(f"\nWHERE THE SAVING COMES FROM — `{real_captures.command('test')}` "
          f"(the two parts sum to the {a_cold - b_filt}-token total)")
    print(f"  persistent session (no server -> server) : {persistent:>7} tokens  "
          f"(boot preamble ~{boot} avoided server-side, net of the warm capture's own terminal noise)")
    print(f"  output filtering (collapse-success)      : {filtering:>7} tokens  "
          f"(226 green tests -> a one-line summary — the dominant win here)")

    # ---- Fixed cost of Arm B, netted out honestly ----
    schema = count(_schema_overhead_text())
    print(f"\nFIXED COST OF ARM B (once per context): ~sbt_execute schema ≈ {schema} tokens (approx)")

    # ---- Session model: a realistic edit loop ----
    nc, nt = args.compiles, args.tests
    ac, _, bc = per_call["compile"]
    at, _, bt = per_call["test"]
    cost_a = nc * ac + nt * at
    cost_b = schema + nc * bc + nt * bt
    print(f"\nSESSION MODEL — an edit loop of {nc} compiles + {nt} test runs")
    print(f"  Arm A  (cold every call)  : {cost_a:>8} tokens  ({nc}x{ac} + {nt}x{at})")
    print(f"  Arm B  (server, filtered) : {cost_b:>8} tokens  (schema {schema} + {nc}x{bc} + {nt}x{bt})")
    if cost_a:
        print(f"  -> Arm B saves {cost_a - cost_b} tokens ({_pct(cost_a, cost_b)}) over the session")

    # Break-even on the cheaper of the two commands (worst case for the server).
    worst_saving = min(ac - bc, at - bt)
    if worst_saving > 0:
        print(f"  break-even: even at the smallest per-call saving ({worst_saving}), the "
              f"{schema}-token schema is repaid within {schema // worst_saving + 1} call(s)")
    else:
        print("  WARNING: a command shows no per-call saving — check the captures")


if __name__ == "__main__":
    main()
