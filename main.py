#!/usr/bin/env python3
"""The GPS Swears It Was a Shortcut -- entry program.

Writes exactly one line (200 characters at most) to
``/output/entry.txt``, for make.fun's "The GPS Swears It Was a Shortcut" bounty.
Pure standard library and fully deterministic: no randomness, no
network access, no clock, no input files. Running it twice produces
byte-identical output.

The joke: the GPS, smug and defensive, blames the map for a
bridge the river took away, then turns the wrong turn into payback
for a driver who mutes it every trip -- the scenic detour past the
lake is the punchline, a fresh detail instead of the usual
recalculating gag.

How this revision is organised
------------------------------
* :data:`ENTRY` -- the single line being entered, kept verbatim.
* :class:`Limits` -- every numeric gate in one frozen dataclass,
  so a limit is changed in exactly one place.
* :class:`EntryError` -- one exception type for every gate failure,
  so ``main`` reports a bad entry the same way every time.
* ``rule_*`` -- each gate is a small predicate-style function that
  raises :class:`EntryError` naming the rule it enforces; ``RULES``
  lists them in the order they run.
* :func:`validate` -- runs ``RULES`` in order, first failure wins.
* :class:`Sink` -- resolves the output location (honouring the
  ``MAKEFUN_OUTPUT_DIR`` override used by the harness) and owns the
  write-then-read-back proof that the file matches ``ENTRY``.
* :func:`report` -- the one-line success report printed on success.
* :func:`main` -- glue: validate, write, verify, report.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ENTRY = (
    "The map promised a bridge, the river disagreed, and since "
    "you mute me every trip, I figured a scenic detour past the "
    "lake was fair payback."
)


@dataclass(frozen=True)
class Limits:
    """The competition's numeric gates, in one place."""

    max_chars: int = 200
    min_chars: int = 1
    min_words: int = 2
    max_words: int = 1000


LIMITS = Limits()

OUTPUT_FILENAME = "entry.txt"
DEFAULT_OUTPUT_DIR = "/output"
OUTPUT_ENV_VAR = "MAKEFUN_OUTPUT_DIR"


class EntryError(ValueError):
    """A gate rule rejected the entry; the message names the rule."""


def _fail(rule: str, detail: str) -> None:
    """Raise the single error type every gate uses."""
    raise EntryError(f"{rule}: {detail}")


def rule_not_empty(entry: str) -> None:
    """Reject blank or whitespace-only entries."""
    if not entry.strip():
        _fail("not-empty", "entry must not be empty or only whitespace")


def rule_single_line(entry: str) -> None:
    """Reject anything that is not exactly one line of text."""
    if "\n" in entry or "\r" in entry:
        _fail("single-line", "entry must be a single line (no line breaks)")


def rule_no_edge_whitespace(entry: str) -> None:
    """Reject leading/trailing spaces that would be invisible in output."""
    if entry != entry.strip():
        _fail("no-edge-whitespace", "entry must not start or end with whitespace")


def rule_length(entry: str, limits: Limits = LIMITS) -> None:
    """Enforce the competition's character gate."""
    if len(entry) < limits.min_chars:
        _fail("length", f"entry is empty, need at least {limits.min_chars} char")
    if len(entry) > limits.max_chars:
        _fail(
            "length",
            f"entry is {len(entry)} chars, over the {limits.max_chars} limit",
        )


def rule_text_safe(entry: str) -> None:
    """Reject control characters and confirm the text is valid UTF-8."""
    entry.encode("utf-8")  # raises UnicodeEncodeError if not valid UTF-8
    bad = [c for c in entry if ord(c) < 0x20 and c != "\t"]
    if bad:
        _fail(
            "text-safe",
            "entry contains control characters: "
            + ", ".join(f"U+{ord(c):04X}" for c in bad),
        )


def rule_word_count(entry: str, limits: Limits = LIMITS) -> None:
    """Enforce the competition's word-count gate."""
    words = entry.split()
    if len(words) < limits.min_words:
        _fail("word-count", f"entry needs at least {limits.min_words} word(s)")
    if len(words) > limits.max_words:
        _fail(
            "word-count",
            f"entry has {len(words)} words, over the {limits.max_words} limit",
        )


def rule_ends_with_period(entry: str) -> None:
    """Sanity check: the line is one finished sentence, so it ends in a stop."""
    if not entry.endswith("."):
        _fail("ends-with-period", "entry should end with a full stop")


def rule_no_double_spaces(entry: str) -> None:
    """Sanity check: no doubled spaces hiding in the middle of the line."""
    if "  " in entry:
        _fail("no-double-spaces", "entry must not contain double spaces")


RULES = (
    rule_not_empty,
    rule_single_line,
    rule_no_edge_whitespace,
    rule_length,
    rule_text_safe,
    rule_word_count,
    rule_ends_with_period,
    rule_no_double_spaces,
)


def validate(entry: str) -> None:
    """Run every gate rule in RULES order; the first failure raises."""
    for rule in RULES:
        rule(entry)


@dataclass(frozen=True)
class Sink:
    """Where the entry file goes, and the proof it landed intact."""

    directory: str
    filename: str = OUTPUT_FILENAME

    @classmethod
    def from_environment(cls) -> "Sink":
        """Honour the harness override, defaulting to /output."""
        return cls(os.environ.get(OUTPUT_ENV_VAR, DEFAULT_OUTPUT_DIR))

    @property
    def path(self) -> Path:
        """The full output path, creating its directory on demand."""
        directory = Path(self.directory)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / self.filename

    def write(self, entry: str) -> Path:
        """Write the entry plus one trailing newline, as UTF-8 text."""
        target = self.path
        target.write_text(entry + "\n", encoding="utf-8", newline="\n")
        return target

    def verify(self, entry: str, target: Path) -> None:
        """Read the file back and prove it is exactly what we intended."""
        written = target.read_text(encoding="utf-8")
        if written != entry + "\n":
            raise EntryError("verify: written entry does not match ENTRY")
        validate(written.rstrip("\n"))


def report(entry: str, target: Path) -> str:
    """Build the one-line success report for the entry."""
    words = len(entry.split())
    return f"wrote {len(entry)} chars ({words} words) to {target}"


def main(argv: list[str] | None = None) -> int:
    """Validate, write, verify, and report. Returns a process exit code."""
    del argv  # no command-line options: the entry is fixed
    sink = Sink.from_environment()
    try:
        validate(ENTRY)
        target = sink.write(ENTRY)
        sink.verify(ENTRY, target)
    except EntryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(report(ENTRY, target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
