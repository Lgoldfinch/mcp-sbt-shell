"""Post-processing of raw sbt output to reduce tokens sent to the MCP client.

Three layers, applied by :func:`clean_output`:

1. Safe cleanup (always) — strips only noise (ANSI/control bytes, carriage-return
   progress redraws, the echoed command, prompt residue, blank-line runs). Never
   removes message content.
2. Success collapse (opt-in) — keyed on the presence of sbt's ``[success]`` token,
   replaces a clean run with a terse one-line marker plus any warnings.
3. Aggressive (opt-in) — a ScalaTest-aware filter that keeps failure signal
   (``*** FAILED ***`` blocks, assertion detail, ``[error]``/``[warn]``) while
   dropping passing-suite chatter. It also drops framework/runtime stack frames
   (keeping the project frame that matters), deduplicates identical traces across
   failures, prepends a recompile-status header, and strips the low-value
   ``[info]`` prefix.

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

# Package prefixes whose stack frames are framework/runtime noise. A frame is
# dropped when its class starts with one of these (unless force-kept by a
# configured KEEP_FRAME_PREFIXES entry). Kept frames are usually the single
# project ``…Test.scala:NNN`` line an engineer actually needs.
_FRAMEWORK_FRAME_PREFIXES = ("org.scalatest", "scala.", "java.", "jdk.", "sbt.")

# Recurring environment preamble that carries no signal and repeats every run.
_ENV_PREAMBLE_RE = re.compile(r"Futhark library up to date:|^\s*WARNING: package .* not in ")

# sbt's incremental-compile announcement, e.g. "compiling 3 Scala sources to …".
_COMPILING_RE = re.compile(r"compiling (\d+) Scala sources?")

# Commands for which a "no recompile (cached)" note is meaningful.
_COMPILE_CMD_RE = re.compile(r"\b(compile|test)", re.IGNORECASE)


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


def _frame_fqcn(stripped_content: str) -> str:
    """Extract the fully-qualified class/method from a ``at pkg.Cls.m(File:NN)`` frame."""
    return stripped_content[3:].split("(", 1)[0].strip()


def _is_framework_frame(stripped_content: str, keep_frame_prefixes: tuple[str, ...]) -> bool:
    """True if this ``at …`` frame is framework noise that should be dropped."""
    fqcn = _frame_fqcn(stripped_content)
    if any(fqcn.startswith(p) for p in keep_frame_prefixes):
        return False  # force-kept by configuration
    return any(fqcn.startswith(p) for p in _FRAMEWORK_FRAME_PREFIXES)


def _failure_test_name(header_content: str) -> str:
    """Parse the failing test name from a ``- name *** FAILED *** (Nms)`` header."""
    name = header_content.split("*** FAILED ***")[0].split("*** ABORTED ***")[0]
    return name.strip().lstrip("-").strip()


def apply_aggressive(text: str, keep_frame_prefixes: tuple[str, ...]) -> tuple[str, int]:
    """ScalaTest-aware filter: keep failure signal, drop passing-suite chatter.

    Failure blocks are segmented so framework stack frames can be dropped (change
    1) and identical traces deduplicated across failures (change 2). Returns
    ``(filtered_text, dropped_line_count)``.
    """
    kept: list[str] = []
    dropped = 0
    seen_traces: dict[tuple[str, ...], str] = {}

    # Current failure block: header line, its test name, and ordered continuation
    # items tagged "msg" (assertion/source/exception header) or "frame".
    block_header: str | None = None
    block_name = ""
    block_items: list[tuple[str, str]] = []

    def flush_block() -> None:
        nonlocal block_header, block_name, block_items
        if block_header is None:
            return
        kept.append(block_header)
        frame_lines = [line for kind, line in block_items if kind == "frame"]
        sig = tuple(line.strip() for line in frame_lines)
        if sig and sig in seen_traces:
            for kind, line in block_items:
                if kind == "msg":
                    kept.append(line)
            kept.append(f'  (same trace as "{seen_traces[sig]}")')
        else:
            if sig:
                seen_traces[sig] = block_name
            kept.extend(line for _, line in block_items)
        block_header = None
        block_name = ""
        block_items = []

    for line in text.split("\n"):
        level, content = _log_level(line)

        if _ENV_PREAMBLE_RE.search(line):
            flush_block()
            dropped += 1
            continue

        if level in ("error", "warn"):
            flush_block()
            kept.append(line)
            continue

        if "*** FAILED ***" in line or "*** ABORTED ***" in line:
            flush_block()
            block_header = line
            block_name = _failure_test_name(content)
            continue

        # Continuation of a failure block: assertion message, source location,
        # exception header, and stack frames are indented under the failing test.
        stripped = content.strip()
        if block_header is not None and (content[:1].isspace() or stripped.startswith("at ")):
            if stripped.startswith("at "):
                if _is_framework_frame(stripped, keep_frame_prefixes):
                    dropped += 1
                else:
                    block_items.append(("frame", line))
            else:
                block_items.append(("msg", line))
            continue
        flush_block()

        if _SUMMARY_RE.search(content):
            kept.append(line)
            continue

        if content.strip() == "":
            kept.append(line)
            continue

        dropped += 1

    flush_block()
    return "\n".join(kept), dropped


def compile_status(text: str, command: str) -> str | None:
    """One-line recompile-status header, or ``None`` when not meaningful.

    Observability only — surfaces whether sbt actually recompiled so a caller can
    tell a fresh result from a cached one. Does not change what sbt runs.
    """
    m = _COMPILING_RE.search(text)
    if m:
        n = int(m.group(1))
        return f"compiled: {n} source" + ("" if n == 1 else "s")
    if _COMPILE_CMD_RE.search(command):
        return "no recompile (cached)"
    return None


def strip_info_prefix(text: str) -> str:
    """Drop the leading ``[info] `` tag from lines, keeping ``[error]``/``[warn]``.

    Preserves the compile-error vs test-output distinction. Must run after the
    tag-aware filters, which rely on the ``[info]`` prefix being present.
    """
    out = []
    for line in text.split("\n"):
        level, content = _log_level(line)
        out.append(content if level == "info" else line)
    return "\n".join(out)


def clean_output(
    text: str,
    *,
    command: str,
    aggressive: bool,
    collapse_success_enabled: bool,
    keep_frame_prefixes: tuple[str, ...],
) -> str:
    """Filter raw sbt output for the MCP client.

    Order: safe cleanup → success collapse (if enabled) → aggressive (if enabled).
    """
    safe = safe_clean(text, command)

    if collapse_success_enabled:
        collapsed = collapse_success(safe, command)
        if collapsed is not None:
            return collapsed

    if aggressive:
        result, dropped = apply_aggressive(safe, keep_frame_prefixes)
        result = collapse_blank_lines(result).strip()
        if dropped:
            marker = _MARKER_HIDDEN.format(n=dropped, s="" if dropped == 1 else "s")
            result = f"{result}\n\n{marker}" if result else marker
        result = strip_info_prefix(result)
        header = compile_status(safe, command)
        if header:
            result = f"{header}\n{result}" if result else header
        return result

    return safe
