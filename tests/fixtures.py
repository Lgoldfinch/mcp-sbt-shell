r"""Representative raw sbt output samples used by the tests.

NOTE: these are SYNTHETIC captures modelled on real sbt / ScalaTest output
(escape codes, carriage-return progress, log tags, prompt residue). Per the
plan they should be replaced with real captures from the team's ScalaTest
project — drop the raw bytes into ``tests/fixtures/*.txt`` and read them here.
The pattern-matching assertions in ``test_output.py`` are what validate that the
filters behave on the real format.
"""

PROMPT = "sbt:my-project> "

# Successful compile, including ANSI erase-line and \r download progress.
COMPILE_CLEAN = (
    "compile\r\n"
    "\x1b[2K[info] compiling 3 Scala sources to /proj/target/scala-2.13/classes ...\n"
    "[info] Downloading foo\r[info] Downloading foo 50%\r[info] Downloaded foo\n"
    "[info] done compiling\n"
    "[success] Total time: 2 s, completed Jan 1, 2026\n"
    "\n\n"
    + PROMPT
)

# Compile that fails.
COMPILE_FAIL = (
    "compile\n"
    "[info] compiling 1 Scala source to /proj/target/scala-2.13/classes ...\n"
    "[error] /proj/src/main/scala/Bar.scala:5:1: not found: value x\n"
    "[error] one error found\n"
    "[error] (Compile / compileIncremental) Compilation failed\n"
    + PROMPT
)

# Passing ScalaTest suite.
TEST_GREEN = (
    "test\n"
    "[info] FooSpec:\n"
    "[info] - should add two numbers\n"
    "[info] - should subtract two numbers\n"
    "[info] Run completed in 120 milliseconds.\n"
    "[info] Tests: succeeded 2, failed 0\n"
    "[success] Total time: 1 s, completed Jan 1, 2026\n"
    + PROMPT
)

# ScalaTest suite with a real assertion failure. The *why* of the failure
# ("2 did not equal 3 (FooSpec.scala:14)") is emitted on [info] lines.
TEST_RED = (
    "testOnly com.example.FooSpec\n"
    "[info] compiling 1 Scala source to /proj/target/scala-2.13/classes ...\n"
    "[info] FooSpec:\n"
    "[info] - should add two numbers *** FAILED ***\n"
    "[info]   2 did not equal 3 (FooSpec.scala:14)\n"
    "[info]   org.scalatest.exceptions.TestFailedException: 2 did not equal 3\n"
    "[info]   at com.example.FooSpec.$anonfun$new$1(FooSpec.scala:14)\n"
    "[info] - should subtract two numbers\n"
    "[info] Run completed in 231 milliseconds.\n"
    "[info] Total number of tests run: 2\n"
    "[info] Tests: succeeded 1, failed 1\n"
    "[error] Failed tests:\n"
    "[error]     com.example.FooSpec\n"
    "[error] (Test / test) sbt.TestsFailedException: Tests unsuccessful\n"
    + PROMPT
)

# Two ScalaTest failures sharing an identical stack trace, each buried under
# ~4 framework/runtime frames (org.scalatest / scala.runtime / java.base). Models
# the real waste: the only frame that matters is the single com.topaz project
# line. Also carries recurring env preamble that should be dropped.
TEST_RED_MULTI = (
    "testOnly com.topaz.ReportTest\n"
    "Futhark library up to date: 1.2.3\n"
    "WARNING: package com.sun.something not in java.base\n"
    "[info] compiling 2 Scala sources to /proj/target/scala-2.13/classes ...\n"
    "[info] done compiling\n"
    "[info] ReportTest:\n"
    "[info] - view forward monthly expiries *** FAILED *** (334 milliseconds)\n"
    "[info]   1 did not equal 3 (PivotReportsComparator.scala:140)\n"
    "[info]   org.scalatest.exceptions.TestFailedException: 1 did not equal 3\n"
    "[info]   at org.scalatest.matchers.MatchersHelper$.indicateFailure(MatchersHelper.scala:397)\n"
    "[info]   at com.topaz.ReportTest.$anonfun$new$1(ReportTest.scala:60)\n"
    "[info]   at scala.runtime.java8.JFunction0$mcV$sp.apply(JFunction0$mcV$sp.scala:18)\n"
    "[info]   at java.base/java.lang.Thread.run(Thread.java:1474)\n"
    "[info] - view forward quarterly expiries *** FAILED *** (210 milliseconds)\n"
    "[info]   2 did not equal 4 (PivotReportsComparator.scala:140)\n"
    "[info]   org.scalatest.exceptions.TestFailedException: 2 did not equal 4\n"
    "[info]   at org.scalatest.matchers.MatchersHelper$.indicateFailure(MatchersHelper.scala:397)\n"
    "[info]   at com.topaz.ReportTest.$anonfun$new$1(ReportTest.scala:60)\n"
    "[info]   at scala.runtime.java8.JFunction0$mcV$sp.apply(JFunction0$mcV$sp.scala:18)\n"
    "[info]   at java.base/java.lang.Thread.run(Thread.java:1474)\n"
    "[info] Run completed in 1 second.\n"
    "[info] Total number of tests run: 5\n"
    "[info] Tests: succeeded 3, failed 2\n"
    "[error] Failed tests:\n"
    "[error]     com.topaz.ReportTest\n"
    "[error] (Test / test) sbt.TestsFailedException: Tests unsuccessful\n"
    + PROMPT
)

ALL = {
    "compile-clean": COMPILE_CLEAN,
    "compile-fail": COMPILE_FAIL,
    "test-green": TEST_GREEN,
    "test-red": TEST_RED,
    "test-red-multi": TEST_RED_MULTI,
}

# The command each fixture was produced by (needed for command-echo stripping).
COMMANDS = {
    "compile-clean": "compile",
    "compile-fail": "compile",
    "test-green": "test",
    "test-red": "testOnly com.example.FooSpec",
    "test-red-multi": "testOnly com.topaz.ReportTest",
}
