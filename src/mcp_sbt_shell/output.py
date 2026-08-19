"""Post-processing of raw sbt output to reduce tokens sent to the MCP client.

Three layers, applied by :func:`clean_output`:

1. Safe cleanup (always) — strips only noise (ANSI/control bytes, carriage-return
   progress redraws, the echoed command, prompt residue, blank-line runs). Never
   removes message content.
2. Success collapse (opt-in) — keyed on the presence of sbt's ``[success]`` token,
   replaces a clean run with a terse one-line marker plus any warnings.
3. Aggressive (opt-in) — a ScalaTest-aware filter that keeps failure signal
   (``*** FAILED ***`` blocks, assertion detail, ``[error]``/``[warn]``) while
   dropping passing-suite chatter.

Whenever a layer drops or compresses content, a machine-actionable marker is
appended so the caller knows to re-run with ``raw=true`` to recover it.
"""

import re

# CSI sequences (e.g. \x1b[2K erase-line, \x1b[?2004h bracketed-paste, \x1b[0m).
_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
# OSC sequences (e.g. window-title \x1b]0;...\x07).
_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
# Any other lone escape + one byte.
_ESC_RE = re.compile(r"\x1b[@-Z\\-_]")

# sbt log-level tag at the start of a line, e.g. "[info] ", "[error] ".
_TAG_RE = re.compile(r"^\[(info|warn|error|success|debug|trace)\] ?(.*)$")

# A leftover interactive prompt line, e.g. "sbt:my-project> ".
_PROMPT_LINE_RE = re.compile(r"^\s*sbt:[^\n]*?>\s*$", re.MULTILINE)

# ScalaTest / sbt summary lines worth keeping even in aggressive mode.
_SUMMARY_RE = re.compile(
    r"Tests?: (succeeded|failed)"
    r"|TESTS? FAILED"
    r"|Total number of tests run"
    r"|Suites?: (completed|aborted)"
    r"|All tests (passed|succeeded)"
    r"|No tests were executed"
    r"|Failed tests:"
)

_MARKER_HIDDEN = "[{n} line{s} hidden — re-run with raw=true for the full log]"
_MARKER_COLLAPSED = "[output collapsed — re-run with raw=true for the full log]"


def strip_ansi(text: str) -> str:
    """Remove ANSI/terminal control sequences that survive ``--no-colors``."""
    text = _CSI_RE.sub("", text)
    text = _OSC_RE.sub("", text)
    return _ESC_RE.sub("", text)


def collapse_carriage_returns(text: str) -> str:
    """Model terminal overwrite: within a line, keep only the final ``\\r`` segment."""
    out = []
    for line in text.split("\n"):
        if "\r" in line:
            line = line.rstrip("\r")
            if "\r" in line:
                line = line.rsplit("\r", 1)[-1]
        out.append(line)
    return "\n".join(out)


def strip_command_echo(text: str, command: str) -> str:
    """Drop the leading line where sbt echoes back the command we sent."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "":
            continue
        if line.strip() == command.strip():
            del lines[i]
        break
    return "\n".join(lines)


def strip_prompt_residue(text: str) -> str:
    """Remove leftover ``sbt:project>`` prompt fragments."""
    return _PROMPT_LINE_RE.sub("", text)


def collapse_blank_lines(text: str) -> str:
    """Collapse runs of blank lines into a single blank line."""
    out = []
    prev_blank = False
    for line in text.split("\n"):
        blank = line.strip() == ""
        if blank and prev_blank:
            continue
        out.append(line)
        prev_blank = blank
    return "\n".join(out)


def safe_clean(text: str, command: str) -> str:
    """The always-on cleanup layer. Removes only noise, never message content."""
    text = strip_ansi(text)
    text = collapse_carriage_returns(text)
    text = strip_command_echo(text, command)
    text = strip_prompt_residue(text)
    text = collapse_blank_lines(text)
    return text.strip()


def _log_level(line: str) -> tuple[str | None, str]:
    """Return ``(level, content)`` splitting off a leading sbt log tag if present."""
    m = _TAG_RE.match(line)
    if m:
        return m.group(1), m.group(2)
    return None, line


def collapse_success(text: str, command: str) -> str | None:
    """Collapse a successful run to a terse marker, or ``None`` if not applicable.

    Keyed on the presence of ``[success]`` (sbt's authoritative success token),
    not on the absence of ``[error]`` — a failing task never prints ``[success]``,
    so this cannot turn a failure into a false "passed". Warnings are preserved.
    """
    if "[success]" not in text:
        return None
    warns = [line for line in text.split("\n") if _log_level(line)[0] == "warn"]

    m = re.search(r"Total time:\s*([^,\n]+)", text)
    time = m.group(1).strip() if m else None
    summary = f"✔ {command.strip()} succeeded" + (f" ({time})" if time else "")

    return "\n".join([*warns, summary, _MARKER_COLLAPSED])


def apply_aggressive(text: str) -> tuple[str, int]:
    """ScalaTest-aware filter: keep failure signal, drop passing-suite chatter.

    Returns ``(filtered_text, dropped_line_count)``.
    """
    kept: list[str] = []
    dropped = 0
    in_failure = False
    for line in text.split("\n"):
        level, content = _log_level(line)

        if level in ("error", "warn"):
            kept.append(line)
            in_failure = False
            continue

        if "*** FAILED ***" in line or "*** ABORTED ***" in line:
            kept.append(line)
            in_failure = True
            continue

        # Continuation of a failure block: assertion message, source location,
        # and stack frames are indented under the failing test.
        if in_failure and (content[:1].isspace() or content.startswith("at ")):
            kept.append(line)
            continue
        in_failure = False

        if _SUMMARY_RE.search(content):
            kept.append(line)
            continue

        if content.strip() == "":
            kept.append(line)
            continue

        dropped += 1

    return "\n".join(kept), dropped


def clean_output(text: str, *, command: str, aggressive: bool, collapse_success_enabled: bool) -> str:
    """Filter raw sbt output for the MCP client.

    Order: safe cleanup → success collapse (if enabled) → aggressive (if enabled).
    """
    safe = safe_clean(text, command)

    if collapse_success_enabled:
        collapsed = collapse_success(safe, command)
        if collapsed is not None:
            return collapsed

    if aggressive:
        result, dropped = apply_aggressive(safe)
        result = collapse_blank_lines(result).strip()
        if dropped:
            marker = _MARKER_HIDDEN.format(n=dropped, s="" if dropped == 1 else "s")
            result = f"{result}\n\n{marker}" if result else marker
        return result

    return safe
