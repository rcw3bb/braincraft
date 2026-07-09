"""
braincraft.ignorefile - Gitignore-style ignore file parser with extensible pattern handlers.

Reads an ignore file and determines whether a given path should be ignored, following
the gitignore pattern specification (https://git-scm.com/docs/gitignore).

Pattern rules supported:
- Blank lines and ``#`` comment lines are skipped.
- A leading ``!`` negates a pattern (re-includes a previously excluded path).
- A trailing ``/`` restricts matching to directories only.
- A pattern without a ``/`` (other than trailing) matches at any directory level.
- A pattern with a ``/`` at the start or middle is anchored to the current working
  directory.
- ``*`` matches anything except ``/``; ``?`` matches any single character except ``/``.
- ``[a-z]`` character range notation is supported.
- ``**`` has special meaning: leading ``**/`` matches in all directories; trailing ``/**``
  matches everything inside a directory; ``/**/`` matches zero or more intermediate
  directories.

Extensibility is provided via :class:`PatternHandler` — register a concrete subclass on
an :class:`IgnoreFile` instance to handle patterns beyond the built-in gitignore rules.

:author: Ron Webb
:since: 1.1.0
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from logenrich import setup_logger

_logger = setup_logger(__name__)


class PatternHandler(ABC):
    """Abstract base class for custom ignore-pattern handlers.

    Register a concrete subclass on an :class:`IgnoreFile` via
    :meth:`IgnoreFile.register_handler`.  Custom handlers are consulted before
    the built-in gitignore handler.  Return ``None`` from :meth:`matches` to
    indicate that the handler does not apply to the given pattern, causing the
    engine to fall through to the next handler or the built-in implementation.

    :author: Ron Webb
    :since: 1.1.0
    """

    @abstractmethod
    def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
        """Determine whether *path* is matched by *pattern*.

        :param pattern: Cleaned pattern string — no leading ``!``, no leading
            or trailing ``/``.
        :param path: Resolved absolute path to test.
        :param base_dir: Current working directory at the time
            :class:`IgnoreFile` was created.
        :return: ``True`` if the path matches, ``False`` if it does not,
            ``None`` if this handler does not apply to the pattern.
        """


@dataclass
class _ParsedLine:
    """Internal representation of a single parsed ignore-file line.

    :author: Ron Webb
    :since: 1.1.0
    """

    negated: bool
    directory_only: bool
    anchored: bool
    pattern: str
    raw: str


def _escape_for_regex(text: str) -> str:
    """Escape a plain string so it is safe for use in a :mod:`re` pattern.

    Only characters that are special in regex *and* are not gitignore
    metacharacters (``*``, ``?``, ``[``, ``]``) are escaped here.  The caller
    is responsible for handling those metacharacters separately.

    :param text: Plain text to escape.
    :return: Regex-safe string.
    """
    special = r"\.^$+{}()|"
    result = []
    for char in text:
        if char in special:
            result.append("\\" + char)
        else:
            result.append(char)
    return "".join(result)


def _compute_anchored(pattern: str) -> bool:
    """Determine whether a gitignore pattern is anchored to the base directory.

    A pattern is anchored when it contains a ``/`` at the start or in the
    middle.  The special leading ``**/`` prefix is *not* considered an anchor
    because it means "match in all directories" and therefore floats freely.

    :param pattern: Cleaned gitignore pattern (leading ``/`` may still be
        present).
    :return: ``True`` if the pattern is anchored.
    """
    if pattern.startswith("**/"):
        return False
    return "/" in pattern


def _segment_to_regex(segment: str) -> str | None:
    """Convert a single (non-``**``) gitignore pattern segment to a regex fragment.

    :param segment: A portion of a gitignore pattern that contains no ``**``
        tokens.
    :return: Regex fragment string, or ``None`` when the segment contains an
        invalid trailing backslash (which should never match).
    """
    part_chars: list[str] = []
    idx = 0
    while idx < len(segment):
        char = segment[idx]
        if char == "*":
            part_chars.append("[^/]*")
        elif char == "?":
            part_chars.append("[^/]")
        elif char == "[":
            end = segment.find("]", idx + 1)
            if end == -1:
                part_chars.append(re.escape("["))
            else:
                part_chars.append(segment[idx : end + 1])
                idx = end
        elif char == "\\":
            idx += 1
            if idx < len(segment):
                part_chars.append(re.escape(segment[idx]))
            else:
                # Trailing backslash — invalid pattern, never matches
                return None
        else:
            part_chars.append(_escape_for_regex(char))
        idx += 1
    return "".join(part_chars)


def _build_regex_body(pat: str) -> str | None:
    """Build the regex body from a normalised gitignore pattern string.

    Handles ``**`` expansion and delegates per-segment conversion to
    :func:`_segment_to_regex`.

    :param pat: Normalised pattern (no leading ``/``, back-slashes replaced by ``/``).
    :return: Regex body string, or ``None`` if the pattern contains an invalid
        trailing backslash.
    """
    segments = re.split(r"(\*\*)", pat)
    regex_parts: list[str] = []

    i = 0
    while i < len(segments):
        seg = segments[i]

        if seg == "**":
            before = segments[i - 1] if i > 0 else ""
            after = segments[i + 1] if i + 1 < len(segments) else ""

            if (before.endswith("/") or before == "") and after.startswith("/"):
                # Leading **/ or middle /**/  -> zero or more intermediate dirs
                segments[i + 1] = after[1:]  # absorb the leading /
                regex_parts.append("(?:.+/)?")
            elif after == "" and before.endswith("/"):
                # Trailing /**  -> match everything inside
                regex_parts.append(".*")
            else:
                # Standalone ** not adjacent to / -> treat as *
                regex_parts.append("[^/]*")
        else:
            converted = _segment_to_regex(seg)
            if converted is None:
                return None
            regex_parts.append(converted)

        i += 1

    return "".join(regex_parts)


def _pattern_to_regex(pattern: str, anchored: bool) -> re.Pattern[str]:
    """Convert a cleaned gitignore *pattern* into a compiled regular expression.

    :param pattern: Cleaned pattern (no leading ``!``, ``/`` or trailing ``/``).
    :param anchored: When ``True`` the pattern is matched relative to the base
        directory (i.e. anchored to the start of the relative path string).
    :return: Compiled :class:`re.Pattern` object.
    """
    # Normalise forward-slashes (patterns always use /)
    pat = pattern.replace("\\", "/")

    # Strip leading / — anchoring is already encoded in the anchored parameter
    if pat.startswith("/"):
        pat = pat[1:]

    body = _build_regex_body(pat)
    if body is None:
        return re.compile(r"(?!)")

    full_pattern = f"^{body}$" if anchored else f"(?:^|.+/){body}$"

    _logger.debug(
        "Pattern %r -> regex %r (anchored=%s)", pattern, full_pattern, anchored
    )
    return re.compile(full_pattern)


class _GitIgnorePatternHandler(PatternHandler):
    """Built-in gitignore-compatible pattern handler.

    Converts gitignore patterns to regular expressions and tests them against
    the path string supplied by :class:`IgnoreFile`.

    :author: Ron Webb
    :since: 1.1.0
    """

    def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
        """Test *path* against the gitignore *pattern*.

        Computes the path string to match against by attempting
        ``path.relative_to(base_dir)``; when the path lies outside *base_dir*
        the full resolved posix path string is used instead.

        :param pattern: Cleaned gitignore pattern.
        :param path: Resolved absolute path to test.
        :param base_dir: Current working directory at the time
            :class:`IgnoreFile` was created.
        :return: ``True`` if the path matches the pattern, ``False`` otherwise.
        """
        try:
            match_str = path.relative_to(base_dir).as_posix()
        except ValueError:
            match_str = path.as_posix()

        anchored = _compute_anchored(pattern)
        compiled = _pattern_to_regex(pattern, anchored)
        result = compiled.search(match_str) is not None
        _logger.debug(
            "match_str=%r pattern=%r anchored=%s -> %s",
            match_str,
            pattern,
            anchored,
            result,
        )
        return result


_BUILTIN_HANDLER: PatternHandler = _GitIgnorePatternHandler()


def _resolve_negation(line: str) -> tuple[str, bool]:
    """Resolve an escape prefix or negation marker at the start of *line*.

    A leading ``\\#`` or ``\\!`` is an escaped literal character; the
    backslash is stripped and no negation is recorded.  A bare leading ``!``
    is a negation marker; it is stripped and ``negated=True`` is returned.

    :param line: Line with trailing spaces already stripped, known to be
        non-empty and not a comment.
    :return: Tuple of ``(cleaned_line, negated)``.
    """
    if line.startswith("\\#") or line.startswith("\\!"):
        return line[1:], False
    if line.startswith("!"):
        return line[1:], True
    return line, False


def _strip_dir_marker(line: str) -> tuple[str, bool]:
    """Strip a trailing ``/`` directory marker from *line*.

    :param line: Pattern line after negation has been resolved.
    :return: Tuple of ``(cleaned_line, directory_only)``.
    """
    if line.endswith("/"):
        return line.rstrip("/"), True
    return line, False


def _parse_single_line(raw: str) -> _ParsedLine | None:
    """Parse a single raw ignore-file line into a :class:`_ParsedLine`.

    Returns ``None`` for blank lines, comment lines, and lines that become
    empty after stripping decorators (e.g. a bare ``/``).

    :param raw: Raw line string with newline characters already removed.
    :return: Parsed line dataclass, or ``None`` if the line should be skipped.
    """
    line = _strip_trailing_spaces(raw)

    if not line or line.startswith("#"):
        return None

    line, negated = _resolve_negation(line)
    line, directory_only = _strip_dir_marker(line)
    anchored = _compute_anchored(line)

    if not line:
        return None

    return _ParsedLine(
        negated=negated,
        directory_only=directory_only,
        anchored=anchored,
        pattern=line,
        raw=raw,
    )


def _parse_ignore_lines(lines: list[str]) -> list[_ParsedLine]:
    """Parse a list of raw lines from an ignore file into :class:`_ParsedLine` objects.

    :param lines: Raw text lines (may include newline characters).
    :return: List of parsed lines; blank lines and comment lines are omitted.
    """
    parsed: list[_ParsedLine] = []
    for raw_line in lines:
        result = _parse_single_line(raw_line.rstrip("\n\r"))
        if result is not None:
            parsed.append(result)
    return parsed


def _strip_trailing_spaces(line: str) -> str:
    """Strip trailing unescaped spaces from *line*.

    Spaces preceded by a backslash (``\\ ``) are retained; the backslash is
    also removed so the space becomes a literal match character.

    :param line: Raw line string (no trailing newline).
    :return: Line with unescaped trailing spaces removed.
    """
    if not line.endswith(" "):
        return line

    # Walk from the end; count consecutive spaces
    i = len(line) - 1
    while i >= 0 and line[i] == " ":
        i -= 1

    # i now points to the last non-space character (or -1)
    # Check if the space run is preceded by a backslash escape
    # Each \<space> pair is a single escaped space
    result_chars = list(line[: i + 1])
    trailing_spaces = line[i + 1 :]

    # Gather escaped spaces from the boundary
    for char in trailing_spaces:
        if result_chars and result_chars[-1] == "\\":
            result_chars[-1] = char  # replace \ with the escaped space
        # else: unescaped trailing space — skip it

    return "".join(result_chars)


class IgnoreFile:
    """Reads an ignore file and determines whether paths should be ignored.

    Anchored patterns (those containing ``/`` at the start or middle) are
    matched relative to *base_dir* (defaults to the **current working
    directory** at construction time).  Unanchored patterns match at any
    directory depth.
    Custom pattern handling can be layered on top via :meth:`register_handler`.

    Example::

        from pathlib import Path
        from braincraft.ignorefile import IgnoreFile

        ig = IgnoreFile(Path(".gitignore"))
        print(ig.is_ignored(Path("dist/output.js")))   # True / False

    :author: Ron Webb
    :since: 1.1.0
    """

    def __init__(
        self, ignore_file: str | Path, base_dir: str | Path | None = None
    ) -> None:
        """Initialise from an ignore file on disk.

        :param ignore_file: Path to the ignore file; a plain :class:`str` is
            accepted and converted to :class:`~pathlib.Path` internally.
        :param base_dir: Base directory used for anchored-pattern matching.
            A plain :class:`str` is accepted and converted to
            :class:`~pathlib.Path` internally.  When ``None`` (the default)
            the current working directory at the time of this call is used.
        :raises FileNotFoundError: If *ignore_file* does not exist.
        """
        self._ignore_file = Path(ignore_file).resolve()
        self._base_dir = (
            Path(base_dir).resolve() if base_dir is not None else Path.cwd().resolve()
        )
        _logger.debug("IgnoreFile base_dir=%s", self._base_dir)

        lines = self._ignore_file.read_text(encoding="utf-8").splitlines(keepends=True)
        self._parsed_lines = _parse_ignore_lines(lines)
        _logger.debug("Parsed %d pattern lines", len(self._parsed_lines))

        self._handlers: list[PatternHandler] = []

    def register_handler(self, handler: PatternHandler) -> None:
        """Register a custom :class:`PatternHandler`.

        Custom handlers are consulted in registration order before the
        built-in gitignore handler.

        :param handler: Concrete :class:`PatternHandler` instance to register.
        """
        self._handlers.append(handler)
        _logger.debug("Registered handler %r", handler)

    def is_ignored(self, path: str | Path) -> bool:
        """Return ``True`` if *path* should be ignored according to the ignore file.

        Matching always occurs regardless of whether *path* is inside or
        outside the current working directory.  When *path* lies outside the
        base directory the full resolved posix path string is used for
        matching; unanchored patterns (e.g. ``*.log``) will still match
        correctly while anchored patterns will not match such paths.

        Directory-only patterns (patterns whose original form ended with ``/``)
        match only when *path* refers to an existing directory.  If *path* does
        not exist or is not a directory, those patterns are skipped entirely —
        there is no fallback to file matching.

        :param path: Path to test (relative or absolute); a plain :class:`str`
            is accepted and converted to :class:`~pathlib.Path` internally.
        :return: ``True`` if the path should be ignored, ``False`` otherwise.
        """
        resolved = Path(path).resolve()
        is_dir = resolved.is_dir()

        ignored = False
        for line in self._parsed_lines:
            if line.directory_only and not is_dir:
                continue

            matched = self._check_match(line, resolved)

            if matched:
                ignored = not line.negated
                _logger.debug(
                    "Pattern %r %s %s -> ignored=%s",
                    line.raw,
                    "negated" if line.negated else "matched",
                    resolved,
                    ignored,
                )

        return ignored

    def _check_match(self, line: _ParsedLine, path: Path) -> bool:
        """Check *line*'s pattern against *path* using registered then built-in handlers.

        :param line: Parsed ignore-file line.
        :param path: Resolved absolute path to test.
        :return: ``True`` if the pattern matches *path*.
        """
        for handler in self._handlers:
            result = handler.matches(line.pattern, path, self._base_dir)
            if result is not None:
                return result
        result = _BUILTIN_HANDLER.matches(line.pattern, path, self._base_dir)
        return bool(result)
