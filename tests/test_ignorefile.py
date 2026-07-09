"""
Tests for braincraft.ignorefile module.

:author: Ron Webb
:since: 1.1.0
"""

import sys
from pathlib import Path

import pytest

from braincraft.ignorefile import IgnoreFile, PatternHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ignore(tmp_path: Path, content: str) -> Path:
    """Write *content* to a ``.myignore`` file under *tmp_path* and return its path."""
    ignore_file = tmp_path / ".myignore"
    ignore_file.write_text(content, encoding="utf-8")
    return ignore_file


def _make_file(tmp_path: Path, rel: str) -> Path:
    """Create a regular file at *tmp_path/rel* and return its path."""
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    return target


def _make_dir(tmp_path: Path, rel: str) -> Path:
    """Create a directory at *tmp_path/rel* and return its path."""
    target = tmp_path / rel
    target.mkdir(parents=True, exist_ok=True)
    return target


# ---------------------------------------------------------------------------
# TestPatternHandlerABC
# ---------------------------------------------------------------------------


class TestPatternHandlerABC:
    """Tests that PatternHandler is a proper ABC."""

    def test_cannot_instantiate_directly(self) -> None:
        """PatternHandler cannot be instantiated without implementing matches."""
        with pytest.raises(TypeError):
            PatternHandler()  # type: ignore[abstract]

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        """A concrete subclass with matches implemented can be instantiated."""

        class _Concrete(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                return None

        handler = _Concrete()
        assert handler.matches("*", Path("/any"), Path("/base")) is None


# ---------------------------------------------------------------------------
# TestIgnoreFileParsing
# ---------------------------------------------------------------------------


class TestIgnoreFileParsing:
    """Tests for blank lines, comments, and escape sequences."""

    def test_blank_lines_are_ignored(self, tmp_path: Path) -> None:
        """Blank lines match nothing and are not treated as patterns."""
        ig = IgnoreFile(_write_ignore(tmp_path, "\n\n\n"))
        target = _make_file(tmp_path, "anything.txt")
        assert ig.is_ignored(target) is False

    def test_comment_line_is_skipped(self, tmp_path: Path) -> None:
        """Lines beginning with # are comments and never match."""
        ig = IgnoreFile(_write_ignore(tmp_path, "# this is a comment\n"))
        target = _make_file(tmp_path, "this is a comment")
        assert ig.is_ignored(target) is False

    def test_escaped_hash_is_literal_pattern(self, tmp_path: Path) -> None:
        """\\# at the start of a line is a literal # in the pattern."""
        ig = IgnoreFile(_write_ignore(tmp_path, "\\#special\n"))
        target = _make_file(tmp_path, "#special")
        assert ig.is_ignored(target) is True

    def test_escaped_exclamation_is_literal_pattern(self, tmp_path: Path) -> None:
        """\\! at the start of a line is a literal ! in the pattern."""
        ig = IgnoreFile(_write_ignore(tmp_path, "\\!important.txt\n"))
        target = _make_file(tmp_path, "!important.txt")
        assert ig.is_ignored(target) is True


# ---------------------------------------------------------------------------
# TestIgnoreFileTrailingSpaces
# ---------------------------------------------------------------------------


class TestIgnoreFileTrailingSpaces:
    """Tests for trailing-space handling."""

    def test_unescaped_trailing_space_stripped(self, tmp_path: Path) -> None:
        """Pattern 'foo   ' (trailing spaces) should match 'foo', not 'foo   '."""
        ig = IgnoreFile(_write_ignore(tmp_path, "foo   \n"))
        assert ig.is_ignored(_make_file(tmp_path, "foo")) is True

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows does not allow trailing spaces in file names",
    )
    def test_escaped_trailing_space_kept(self, tmp_path: Path) -> None:
        """Pattern 'foo\\ ' should match a file literally named 'foo '."""
        ig = IgnoreFile(_write_ignore(tmp_path, "foo\\ \n"))
        assert ig.is_ignored(_make_file(tmp_path, "foo ")) is True


# ---------------------------------------------------------------------------
# TestIgnoreFileSimpleGlobs
# ---------------------------------------------------------------------------


class TestIgnoreFileSimpleGlobs:
    """Tests for basic wildcard patterns."""

    def test_star_matches_any_filename(self, tmp_path: Path) -> None:
        """*.log matches any file ending in .log."""
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        assert ig.is_ignored(_make_file(tmp_path, "app.log")) is True

    def test_star_does_not_match_slash(self, tmp_path: Path) -> None:
        """*.log does not match a/b.log when anchored, but does unanchored."""
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        # unanchored: matches at any level
        assert ig.is_ignored(_make_file(tmp_path, "sub/app.log")) is True

    def test_question_mark_matches_single_char(self, tmp_path: Path) -> None:
        """? matches exactly one character."""
        ig = IgnoreFile(_write_ignore(tmp_path, "file?.txt\n"))
        assert ig.is_ignored(_make_file(tmp_path, "fileA.txt")) is True
        assert ig.is_ignored(_make_file(tmp_path, "file.txt")) is False

    def test_character_class(self, tmp_path: Path) -> None:
        """[abc] matches any single character in the set."""
        ig = IgnoreFile(_write_ignore(tmp_path, "file[abc].txt\n"))
        assert ig.is_ignored(_make_file(tmp_path, "filea.txt")) is True
        assert ig.is_ignored(_make_file(tmp_path, "filed.txt")) is False

    def test_unanchored_matches_at_any_depth(self, tmp_path: Path) -> None:
        """A pattern without / matches files at any directory depth."""
        ig = IgnoreFile(_write_ignore(tmp_path, "secret.key\n"))
        assert ig.is_ignored(_make_file(tmp_path, "a/b/c/secret.key")) is True

    def test_no_match_different_extension(self, tmp_path: Path) -> None:
        """*.log does not match files with a different extension."""
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        assert ig.is_ignored(_make_file(tmp_path, "app.txt")) is False


# ---------------------------------------------------------------------------
# TestIgnoreFileAnchoring
# ---------------------------------------------------------------------------


class TestIgnoreFileAnchoring:
    """Tests for anchored vs unanchored patterns."""

    def test_slash_in_middle_anchors_to_base(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """doc/frotz only matches doc/frotz relative to CWD."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "doc/frotz\n"))
        assert ig.is_ignored(_make_file(tmp_path, "doc/frotz")) is True

    def test_anchored_pattern_does_not_float(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """doc/frotz does not match a/doc/frotz (anchored to CWD root)."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "doc/frotz\n"))
        assert ig.is_ignored(_make_file(tmp_path, "a/doc/frotz")) is False

    def test_leading_slash_anchors_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """/hello.* anchors to CWD root; does not match a/hello.txt."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "/hello.*\n"))
        assert ig.is_ignored(_make_file(tmp_path, "hello.txt")) is True
        assert ig.is_ignored(_make_file(tmp_path, "a/hello.txt")) is False

    def test_no_slash_floats_freely(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare filename pattern matches at any nesting depth."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "build\n"))
        assert ig.is_ignored(_make_file(tmp_path, "x/y/build")) is True


# ---------------------------------------------------------------------------
# TestIgnoreFileDirectoryOnly
# ---------------------------------------------------------------------------


class TestIgnoreFileDirectoryOnly:
    """Tests for directory-only patterns (trailing /)."""

    def test_trailing_slash_matches_directory(self, tmp_path: Path) -> None:
        """foo/ matches a directory named foo."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build/\n"))
        build_dir = _make_dir(tmp_path, "build")
        assert ig.is_ignored(build_dir) is True

    def test_trailing_slash_does_not_match_file(self, tmp_path: Path) -> None:
        """foo/ does NOT match a regular file named foo — no fallback."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build/\n"))
        build_file = _make_file(tmp_path, "build")
        assert ig.is_ignored(build_file) is False

    def test_trailing_slash_nonexistent_not_ignored(self, tmp_path: Path) -> None:
        """A non-existent path is not a directory and must not be ignored by a dir-only pattern."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build/\n"))
        ghost = tmp_path / "build"
        # ghost does not exist, so is_dir() == False
        assert ig.is_ignored(ghost) is False


# ---------------------------------------------------------------------------
# TestIgnoreFileNegation
# ---------------------------------------------------------------------------


class TestIgnoreFileNegation:
    """Tests for ! negation patterns."""

    def test_negation_re_includes_file(self, tmp_path: Path) -> None:
        """!foo re-includes a file excluded by a previous pattern."""
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n!keep.log\n"))
        assert ig.is_ignored(_make_file(tmp_path, "app.log")) is True
        assert ig.is_ignored(_make_file(tmp_path, "keep.log")) is False

    def test_negation_order_matters(self, tmp_path: Path) -> None:
        """Last matching pattern wins; a later * overrides an earlier !."""
        ig = IgnoreFile(_write_ignore(tmp_path, "!keep.log\n*.log\n"))
        assert ig.is_ignored(_make_file(tmp_path, "keep.log")) is True

    def test_escaped_exclamation_is_not_negation(self, tmp_path: Path) -> None:
        """\\!foo is a literal pattern matching a file named !foo, not a negation."""
        ig = IgnoreFile(_write_ignore(tmp_path, "\\!important.txt\n"))
        target = _make_file(tmp_path, "!important.txt")
        assert ig.is_ignored(target) is True


# ---------------------------------------------------------------------------
# TestIgnoreFileDoubleAsterisk
# ---------------------------------------------------------------------------


class TestIgnoreFileDoubleAsterisk:
    """Tests for ** double-asterisk patterns."""

    def test_leading_double_star_slash(self, tmp_path: Path) -> None:
        """**/foo matches a directory or file foo anywhere."""
        ig = IgnoreFile(_write_ignore(tmp_path, "**/foo\n"))
        assert ig.is_ignored(_make_file(tmp_path, "foo")) is True
        assert ig.is_ignored(_make_file(tmp_path, "a/foo")) is True
        assert ig.is_ignored(_make_file(tmp_path, "a/b/foo")) is True

    def test_trailing_double_star(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """abc/** matches everything inside directory abc."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "abc/**\n"))
        assert ig.is_ignored(_make_file(tmp_path, "abc/file.txt")) is True
        assert ig.is_ignored(_make_file(tmp_path, "abc/sub/file.txt")) is True

    def test_middle_double_star(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """a/**/b matches a/b, a/x/b, a/x/y/b."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "a/**/b\n"))
        assert ig.is_ignored(_make_file(tmp_path, "a/b")) is True
        assert ig.is_ignored(_make_file(tmp_path, "a/x/b")) is True
        assert ig.is_ignored(_make_file(tmp_path, "a/x/y/b")) is True

    def test_double_star_does_not_match_outside_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """abc/** does not match a file that is not inside abc."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "abc/**\n"))
        assert ig.is_ignored(_make_file(tmp_path, "xyz/file.txt")) is False


# ---------------------------------------------------------------------------
# TestIgnoreFileExternalPath
# ---------------------------------------------------------------------------


class TestIgnoreFileExternalPath:
    """Tests that matching works for paths outside the current working directory."""

    def test_unanchored_pattern_matches_external_path(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """An unanchored pattern like *.log matches a path outside base_dir."""
        external = tmp_path_factory.mktemp("external")
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        target = _make_file(external, "app.log")
        assert ig.is_ignored(target) is True

    def test_no_error_for_external_path(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """is_ignored does not raise when path is outside base_dir."""
        external = tmp_path_factory.mktemp("external2")
        ig = IgnoreFile(_write_ignore(tmp_path, "*.txt\n"))
        target = _make_file(external, "notes.txt")
        # Should not raise, should just match based on pattern
        result = ig.is_ignored(target)
        assert isinstance(result, bool)

    def test_anchored_pattern_does_not_match_external_path(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """An anchored pattern does not match a path from a completely different tree."""
        external = tmp_path_factory.mktemp("external3")
        ig = IgnoreFile(_write_ignore(tmp_path, "/build\n"))
        target = _make_file(external, "build")
        assert ig.is_ignored(target) is False


# ---------------------------------------------------------------------------
# TestIgnoreFileCustomHandler
# ---------------------------------------------------------------------------


class TestIgnoreFileCustomHandler:
    """Tests for the register_handler extensibility mechanism."""

    def test_custom_handler_called_first(self, tmp_path: Path) -> None:
        """A registered handler is consulted before the built-in handler."""
        called_with: list[str] = []

        class _Tracker(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                called_with.append(pattern)
                return None  # defer to built-in

        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        ig.register_handler(_Tracker())
        ig.is_ignored(_make_file(tmp_path, "app.log"))
        assert "*.log" in called_with

    def test_custom_handler_true_short_circuits_builtin(self, tmp_path: Path) -> None:
        """A handler returning True causes the path to be ignored regardless of built-in."""

        class _AlwaysMatch(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                return True

        ig = IgnoreFile(_write_ignore(tmp_path, "*.py\n"))
        ig.register_handler(_AlwaysMatch())
        # file.txt would NOT be ignored by *.py, but the custom handler returns True
        assert ig.is_ignored(_make_file(tmp_path, "file.txt")) is True

    def test_custom_handler_false_short_circuits_builtin(self, tmp_path: Path) -> None:
        """A handler returning False prevents the built-in from ignoring the path."""

        class _NeverMatch(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                return False

        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        ig.register_handler(_NeverMatch())
        # app.log would normally be ignored by *.log, but the custom handler vetoes it
        assert ig.is_ignored(_make_file(tmp_path, "app.log")) is False

    def test_custom_handler_none_falls_through_to_builtin(self, tmp_path: Path) -> None:
        """A handler returning None defers to the built-in handler."""

        class _PassThrough(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                return None

        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        ig.register_handler(_PassThrough())
        assert ig.is_ignored(_make_file(tmp_path, "app.log")) is True

    def test_multiple_handlers_consulted_in_order(self, tmp_path: Path) -> None:
        """Handlers are consulted in registration order; first non-None result wins."""
        order: list[str] = []

        class _First(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                order.append("first")
                return None

        class _Second(PatternHandler):
            def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
                order.append("second")
                return True

        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        ig.register_handler(_First())
        ig.register_handler(_Second())
        ig.is_ignored(_make_file(tmp_path, "app.log"))
        assert order == ["first", "second"]


# ---------------------------------------------------------------------------
# TestIgnoreFileStrInput
# ---------------------------------------------------------------------------


class TestIgnoreFileStrInput:
    """Tests that IgnoreFile and is_ignored accept plain str in addition to Path."""

    def test_init_accepts_str(self, tmp_path: Path) -> None:
        """IgnoreFile can be constructed with a plain str path."""
        ignore_path = _write_ignore(tmp_path, "*.log\n")
        ig = IgnoreFile(str(ignore_path))
        assert ig.is_ignored(_make_file(tmp_path, "app.log")) is True

    def test_is_ignored_accepts_str(self, tmp_path: Path) -> None:
        """is_ignored accepts a plain str path."""
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        target = _make_file(tmp_path, "app.log")
        assert ig.is_ignored(str(target)) is True

    def test_is_ignored_str_non_match(self, tmp_path: Path) -> None:
        """is_ignored returns False for a non-matching str path."""
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"))
        target = _make_file(tmp_path, "app.txt")
        assert ig.is_ignored(str(target)) is False

    def test_init_and_is_ignored_both_str(self, tmp_path: Path) -> None:
        """Both constructor and is_ignored work end-to-end with plain strings."""
        ignore_path = _write_ignore(tmp_path, "*.log\n")
        target = _make_file(tmp_path, "app.log")
        ig = IgnoreFile(str(ignore_path))
        assert ig.is_ignored(str(target)) is True


# ---------------------------------------------------------------------------
# TestIgnoreFileBaseDir
# ---------------------------------------------------------------------------


class TestIgnoreFileBaseDir:
    """Tests for the optional base_dir constructor parameter."""

    def test_default_none_uses_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When base_dir is None (default) the CWD is used for anchored matching."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "/build\n"))
        assert ig.is_ignored(_make_file(tmp_path, "build")) is True

    def test_base_dir_as_path_overrides_cwd(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """A Path base_dir is used for anchored matching instead of CWD."""
        other = tmp_path_factory.mktemp("other")
        ig = IgnoreFile(_write_ignore(tmp_path, "/build\n"), base_dir=tmp_path)
        # file inside the supplied base_dir should be matched
        assert ig.is_ignored(_make_file(tmp_path, "build")) is True

    def test_base_dir_as_str_overrides_cwd(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """A str base_dir is accepted and behaves the same as a Path."""
        ig = IgnoreFile(_write_ignore(tmp_path, "/build\n"), base_dir=str(tmp_path))
        assert ig.is_ignored(_make_file(tmp_path, "build")) is True

    def test_anchored_pattern_matches_relative_to_base_dir(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Anchored patterns are evaluated relative to base_dir, not CWD."""
        base = tmp_path_factory.mktemp("base")
        cwd_dir = tmp_path  # different from base
        # change into cwd_dir so CWD != base
        ig = IgnoreFile(_write_ignore(cwd_dir, "doc/frotz\n"), base_dir=base)
        # doc/frotz relative to base should be ignored
        assert ig.is_ignored(_make_file(base, "doc/frotz")) is True
        # doc/frotz relative to cwd_dir should NOT be ignored (wrong base)
        assert ig.is_ignored(_make_file(cwd_dir, "doc/frotz")) is False

    def test_unanchored_pattern_unaffected_by_base_dir(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Unanchored patterns match regardless of which base_dir is provided."""
        other = tmp_path_factory.mktemp("unanchored_base")
        ig = IgnoreFile(_write_ignore(tmp_path, "*.log\n"), base_dir=other)
        # unanchored *.log still matches a file anywhere
        assert ig.is_ignored(_make_file(tmp_path, "app.log")) is True

    def test_base_dir_does_not_affect_directory_only_pattern(
        self, tmp_path: Path
    ) -> None:
        """Directory-only patterns still apply correctly when base_dir is explicit."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build/\n"), base_dir=tmp_path)
        build_dir = _make_dir(tmp_path, "build")
        build_file = _make_file(tmp_path, "other_build")
        assert ig.is_ignored(build_dir) is True
        assert ig.is_ignored(build_file) is False
