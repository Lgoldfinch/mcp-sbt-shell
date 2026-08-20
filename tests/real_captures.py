r"""Loaders for REAL sbt captures from the topaz-d worktree (not synthetic).

For each command we hold two captures in ``tests/fixtures/``:

* ``cold-<cmd>.txt`` — a cold ``sbt "<cmd>"`` run: the full stdout+stderr a plain
  Bash call returns to Claude when there is NO server. Includes the whole boot
  preamble (``welcome to sbt`` … ``resolving key references`` …
  ``set current project``), because every cold invocation replays it.
* ``warm-<cmd>.txt`` — ONE persistent sbt shell that issues the command (plus a
  couple of neighbours). The boot preamble appears once, at the top; each
  command's output is delimited by sbt's bracketed-paste prompt residue — the
  exact byte sequence the server keys on (``SbtSession.prompt`` in
  ``sbt_session.py``). Splitting on it reconstructs, per command, precisely what
  ``SbtSession.execute`` hands to ``clean_output`` — so Arm B is faithful to the
  running server.

Captured commands (topaz-d, quantity module):

* ``quantity / compile`` — a real 31-source compile (``clean`` first to force it).
* ``quantity / test``    — 226 tests, all green (exercises ``--collapse-success``).

Caveat: captured through a pipe, not with the server's
``--no-colors --supershell=false`` flags, so they carry slightly MORE ANSI noise
than the live server would. That only understates the server's advantage.
"""

import os

_HERE = os.path.dirname(__file__)
_FIX = os.path.join(_HERE, "fixtures")

# The prompt residue sbt emits before reading each command. Identical to the
# bytes SbtSession waits on: ESC [ ? 2 0 0 4 h > . . . .
_PROMPT_DELIM = "\x1b[?2004h>...."


# For each logical command: the cold capture, the warm capture, and the exact
# sequence of commands issued into that warm shell (so we can label segments).
CASES = {
    "compile": {
        "command": "quantity / compile",
        "cold": "cold-compile.txt",
        "warm_file": "warm-compile-green.txt",
        "warm_commands": ["quantity / clean", "quantity / compile", "exit"],
    },
    "test": {
        "command": "quantity / test",
        "cold": "cold-test-green.txt",
        "warm_file": "warm-test-green.txt",
        "warm_commands": ["quantity / test", "exit"],
    },
}


def _read(name: str) -> str:
    with open(os.path.join(_FIX, name), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _segments(warm_file: str, warm_commands: list[str]) -> tuple[str, list[tuple[str, str]]]:
    """Split a warm capture into ``(boot_preamble, [(command, output), ...])``."""
    segs = _read(warm_file).split(_PROMPT_DELIM)
    boot = segs[0]
    turns = list(zip(warm_commands, segs[1:], strict=False))
    return boot, turns


def cold(case: str) -> str:
    """Arm A: raw stdout of the cold ``sbt "<cmd>"`` call (boot preamble included)."""
    return _read(CASES[case]["cold"])


def warm(case: str) -> str:
    """Arm B: the raw output segment for this command from a warm session (no boot)."""
    spec = CASES[case]
    _boot, turns = _segments(spec["warm_file"], spec["warm_commands"])
    for command, output in turns:
        if command == spec["command"]:
            return output
    raise AssertionError(f"no {spec['command']!r} segment in {spec['warm_file']}")


def command(case: str) -> str:
    return CASES[case]["command"]


def boot_preamble() -> str:
    """The one-time boot output. Cold arms replay this on EVERY call; the persistent
    session pays it once, server-side, and it never reaches the model."""
    spec = CASES["compile"]
    boot, _turns = _segments(spec["warm_file"], spec["warm_commands"])
    return boot
