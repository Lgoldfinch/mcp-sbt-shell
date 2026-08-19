from mcp_sbt_shell.output import (
    clean_output,
    collapse_carriage_returns,
    safe_clean,
    strip_ansi,
)

from . import fixtures


def _clean(name, *, aggressive=False, collapse=False):
    return clean_output(
        fixtures.ALL[name],
        command=fixtures.COMMANDS[name],
        aggressive=aggressive,
        collapse_success_enabled=collapse,
    )


# --- safe cleanup ----------------------------------------------------------


def test_strip_ansi_removes_erase_line():
    assert "\x1b" not in strip_ansi("\x1b[2K[info] hi\x1b[0m")
    assert strip_ansi("\x1b[2K[info] hi") == "[info] hi"


def test_collapse_carriage_returns_keeps_final_segment():
    assert collapse_carriage_returns("a\rb\rc") == "c"
    # trailing CR (CRLF) must not wipe the line
    assert collapse_carriage_returns("done\r") == "done"


def test_safe_clean_strips_noise_but_keeps_content():
    out = _clean("compile-clean")
    assert "\x1b" not in out and "\r" not in out
    # echoed command and prompt residue gone
    assert not out.startswith("compile")
    assert "sbt:my-project>" not in out
    # progress redraw collapsed to final state
    assert "Downloaded foo" in out
    assert "50%" not in out
    # real content preserved
    assert "[success] Total time: 2 s" in out


def test_safe_clean_preserves_all_failure_detail():
    out = _clean("test-red")
    for line in [
        "2 did not equal 3 (FooSpec.scala:14)",
        "[error] Failed tests:",
        "should subtract two numbers",
    ]:
        assert line in out


def test_safe_clean_is_idempotent():
    once = safe_clean(fixtures.TEST_RED, "testOnly com.example.FooSpec")
    twice = safe_clean(once, "testOnly com.example.FooSpec")
    assert once == twice


# --- aggressive (ScalaTest-aware) -----------------------------------------


def test_aggressive_keeps_failure_why_drops_passing():
    out = _clean("test-red", aggressive=True)
    # the *why* survives inline — no re-run needed
    assert "2 did not equal 3 (FooSpec.scala:14)" in out
    assert "at com.example.FooSpec" in out
    # errors and the summary survive
    assert "[error] Failed tests:" in out
    assert "Tests: succeeded 1, failed 1" in out
    # passing-test chatter is dropped
    assert "should subtract two numbers" not in out
    assert "compiling 1 Scala source" not in out


def test_aggressive_emits_accurate_hidden_marker():
    out = _clean("test-red", aggressive=True)
    # dropped: compiling, "FooSpec:", passing test, "Run completed" = 4
    assert "4 lines hidden" in out
    assert "raw=true" in out


def test_aggressive_never_drops_errors_or_warns():
    out = _clean("compile-fail", aggressive=True)
    assert "not found: value x" in out
    assert "Compilation failed" in out


# --- success collapse ------------------------------------------------------


def test_collapse_success_on_green_run():
    out = _clean("test-green", collapse=True)
    assert out.startswith("✔ test succeeded (1 s)")
    assert "raw=true" in out
    # the passing-test lines are gone
    assert "should add two numbers" not in out


def test_collapse_keyed_on_success_not_error_absence():
    # test-red has no [success] -> must NOT collapse into a false pass
    out = _clean("test-red", collapse=True)
    assert "succeeded" not in out.splitlines()[0]
    assert "2 did not equal 3 (FooSpec.scala:14)" in out


def test_collapse_does_not_fire_on_failed_compile():
    out = _clean("compile-fail", collapse=True)
    assert "Compilation failed" in out
    assert "✔" not in out


# --- raw escape hatch is the server's job; here we assert filtering shrinks -


def test_filtering_reduces_size():
    for name in fixtures.ALL:
        raw = fixtures.ALL[name]
        assert len(_clean(name, aggressive=True, collapse=True)) <= len(raw)
