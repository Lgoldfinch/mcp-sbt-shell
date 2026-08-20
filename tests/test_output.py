import os

from mcp_sbt_shell.output import (
    clean_output,
    collapse_carriage_returns,
    safe_clean,
    strip_ansi,
)

from . import fixtures

_REAL_RED_CMD = "kerneltests/testOnly com.topaz.kernel.pivot.FuturesExpiriesTableBuilderTest"


def _real_red() -> str:
    path = os.path.join(os.path.dirname(__file__), "fixtures", "cold-test-red.txt")
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _clean(name, *, aggressive=False, collapse=False, keep_frame_prefixes=()):
    return clean_output(
        fixtures.ALL[name],
        command=fixtures.COMMANDS[name],
        aggressive=aggressive,
        collapse_success_enabled=collapse,
        keep_frame_prefixes=keep_frame_prefixes,
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


# --- framework-frame stripping --------------------------------------------


def test_aggressive_drops_framework_frames_keeps_project_frame():
    out = _clean("test-red-multi", aggressive=True)
    # the one frame that matters survives
    assert "at com.topaz.ReportTest.$anonfun$new$1(ReportTest.scala:60)" in out
    # framework/runtime frames are gone
    assert "org.scalatest.matchers.MatchersHelper" not in out
    assert "scala.runtime.java8" not in out
    assert "java.base/java.lang.Thread.run" not in out
    # the assertion detail and exception header are still there
    assert "1 did not equal 3 (PivotReportsComparator.scala:140)" in out
    assert "org.scalatest.exceptions.TestFailedException: 1 did not equal 3" in out


def test_keep_frame_prefixes_override_forces_frame_kept():
    out = _clean(
        "test-red-multi", aggressive=True, keep_frame_prefixes=("org.scalatest.matchers",)
    )
    # normally dropped, but force-kept by configuration
    assert "org.scalatest.matchers.MatchersHelper$.indicateFailure" in out


# --- trace deduplication ---------------------------------------------------


def test_aggressive_dedupes_identical_traces():
    out = _clean("test-red-multi", aggressive=True)
    # the project frame appears once; the repeat is replaced by a back-reference
    assert out.count("at com.topaz.ReportTest.$anonfun$new$1(ReportTest.scala:60)") == 1
    assert '(same trace as "view forward monthly expiries")' in out
    # the second failure keeps its own header and assertion message
    assert "view forward quarterly expiries" in out
    assert "2 did not equal 4 (PivotReportsComparator.scala:140)" in out


# --- recompile-status header ----------------------------------------------


def test_compile_status_header_reports_recompile():
    out = _clean("test-red-multi", aggressive=True)
    assert out.startswith("compiled: 2 sources")


def test_compile_status_header_singular():
    out = _clean("test-red", aggressive=True)
    assert out.startswith("compiled: 1 source\n")


def test_compile_status_no_recompile_when_cached():
    # test-green collapses via success; use aggressive-only on a cached compile
    text = "compile\n[info] done.\n[success] Total time: 0 s\n" + fixtures.PROMPT
    out = clean_output(
        text, command="compile", aggressive=True, collapse_success_enabled=False, keep_frame_prefixes=()
    )
    assert "no recompile (cached)" in out


# --- [info] prefix / env preamble stripping --------------------------------


def test_strips_info_prefix_keeps_error_and_warn():
    out = _clean("test-red-multi", aggressive=True)
    assert "[info]" not in out
    # error tag is preserved (compile-error vs test-output distinction)
    assert "[error] Failed tests:" in out


def test_env_preamble_dropped():
    out = _clean("test-red-multi", aggressive=True)
    assert "Futhark library up to date" not in out
    assert "WARNING: package" not in out


# --- token reduction acceptance -------------------------------------------


def test_multi_failure_output_is_small():
    raw = fixtures.TEST_RED_MULTI
    out = _clean("test-red-multi", aggressive=True)
    # well over half the characters removed, signal retained
    assert len(out) < len(raw) * 0.5


# --- real capture: 2-failure testOnly with full ~90-frame traces -----------


def _clean_real(**kwargs):
    return clean_output(
        _real_red(),
        command=_REAL_RED_CMD,
        aggressive=True,
        collapse_success_enabled=True,
        **kwargs,
    )


def test_real_capture_cut_well_over_half():
    raw = _real_red()
    out = _clean_real(keep_frame_prefixes=())
    # ~12k-token brief; this 2-failure capture is ~6.8k tokens raw. Target well
    # over half off. (char/4 proxy tracks tokens closely enough for a guard.)
    assert len(out) < len(raw) * 0.5


def test_real_capture_retains_all_signal():
    out = _clean_real(keep_frame_prefixes=())
    # both failing test names
    assert "uploaded expiries should supersede expiry rules" in out
    assert "months with uploaded expiries show Uploaded source" in out
    # the assertion message and its comparator source location
    assert '"[B]" was not equal to "[Rules]" (PivotReportsComparator.scala:123)' in out
    # the project source locations of each failing test body
    assert "FuturesExpiriesTableBuilderTest.scala:218" in out
    assert "FuturesExpiriesTableBuilderTest.scala:265" in out
    # Expected/Actual essence survives (item 3 truncation deliberately not done)
    assert "Expected" in out and "Actual" in out
    # recompile status + native summary
    assert out.startswith("compiled: 2 sources")
    assert "Tests: succeeded 7, failed 2" in out
    assert "[error] Failed tests:" in out


def test_real_capture_compacts_repeated_source_locations():
    out = _clean_real(keep_frame_prefixes=())
    # the FreeSpec lifecycle overrides all report the class declaration line (:24);
    # each trace keeps only the first, so at most one per failure survives (<= 2).
    assert out.count("FuturesExpiriesTableBuilderTest.scala:24)") <= 2
    # but the distinct, useful project locations are never dropped
    assert "FuturesExpiriesTableBuilderTest.scala:218" in out
    assert "FuturesExpiriesTableBuilderTest.scala:265" in out
    assert "PivotReportsComparator.scala:123" in out


def test_real_capture_drops_framework_and_preamble():
    out = _clean_real(keep_frame_prefixes=())
    for noise in (
        "org.scalatest.SuperEngine",
        "org.scalatest.freespec.AnyFreeSpecLike",
        "java.base/java.util.concurrent",
        "sbt.ForkMain",
        "scala.collection.immutable.Vector.foreach",
        "Futhark library up to date",
        "WARNING: package",
        "Generating Apache Pekko gRPC",
        "[info]",
    ):
        assert noise not in out
