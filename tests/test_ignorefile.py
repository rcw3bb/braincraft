"""
Tests for braincraft.ignorefile module.

:author: Ron Webb
:since: 1.1.0
"""

import sys
from pathlib import Path

import pytest

from braincraft.ignorefile import IgnoreFile, PatternHandler, _to_path

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


@pytest.fixture
def gosu_xyz_ignore_file(tmp_path: Path) -> Path:
    """Ignore file with a single anchored directory pattern: ``gosu/xyz/``."""
    return _write_ignore(tmp_path, "gosu/xyz/\n")


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
    """Tests for directory-only patterns (trailing / or \\)."""

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

    def test_trailing_backslash_matches_directory(self, tmp_path: Path) -> None:
        """foo\\ matches a directory named foo, same as foo/."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build\\\n"))
        build_dir = _make_dir(tmp_path, "build")
        assert ig.is_ignored(build_dir) is True

    def test_trailing_backslash_does_not_match_file(self, tmp_path: Path) -> None:
        """foo\\ does NOT match a regular file named foo — no fallback."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build\\\n"))
        build_file = _make_file(tmp_path, "build")
        assert ig.is_ignored(build_file) is False

    def test_ignored_directory_cascades_to_all_contents(self, tmp_path: Path) -> None:
        """When base_dir contains an ignored directory, all its files/dirs are ignored too."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build/\n"), base_dir=tmp_path)
        nested_file = _make_file(tmp_path, "build/output.txt")
        nested_dir = _make_dir(tmp_path, "build/sub")
        assert ig.is_ignored(nested_file) is True
        assert ig.is_ignored(nested_dir) is True

    def test_is_ignored_file_path_under_ignored_directory(self, tmp_path: Path) -> None:
        """is_ignored ignores a file path whose path contains an ignored directory."""
        ig = IgnoreFile(_write_ignore(tmp_path, "build/\n"))
        deep_file = _make_file(tmp_path, "build/sub/deep/file.txt")
        assert ig.is_ignored(deep_file) is True


# ---------------------------------------------------------------------------
# TestIgnoreFileMultiLevelSeparatorEquivalence
# ---------------------------------------------------------------------------


class TestIgnoreFileMultiLevelSeparatorEquivalence:
    """Tests that \\ and / are interchangeable as multi-level directory separators."""

    def test_to_path_normalizes_backslash_string(self) -> None:
        """_to_path treats \\ as a path separator in a plain str, regardless of OS."""
        assert _to_path("dir1\\dir2\\file.txt").parts[-3:] == (
            "dir1",
            "dir2",
            "file.txt",
        )

    def test_to_path_leaves_path_object_unchanged(self, tmp_path: Path) -> None:
        """_to_path returns a Path object as-is without touching its separators."""
        assert _to_path(tmp_path) == tmp_path

    def test_base_dir_backslash_string_with_forward_slash_pattern(
        self, tmp_path: Path
    ) -> None:
        """A base_dir string using \\ still anchors a pattern written with /."""
        base_dir_str = str(tmp_path).replace("/", "\\")
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1/dir2/\n"), base_dir=base_dir_str)
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig.is_ignored(nested_file) is True

    def test_base_dir_forward_slash_string_with_backslash_pattern(
        self, tmp_path: Path
    ) -> None:
        """A base_dir string using / still anchors a pattern written with \\."""
        base_dir_str = str(tmp_path).replace("\\", "/")
        ig = IgnoreFile(
            _write_ignore(tmp_path, "dir1\\dir2\\\n"), base_dir=base_dir_str
        )
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig.is_ignored(nested_file) is True

    def test_forward_slash_pattern_matches_nested_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dir1/dir2/ matches the nested directory dir1/dir2."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1/dir2/\n"))
        nested_dir = _make_dir(tmp_path, "dir1/dir2")
        assert ig.is_ignored(nested_dir) is True

    def test_backslash_pattern_matches_nested_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dir1\\dir2\\ matches the nested directory dir1/dir2, same as dir1/dir2/."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1\\dir2\\\n"))
        nested_dir = _make_dir(tmp_path, "dir1/dir2")
        assert ig.is_ignored(nested_dir) is True

    def test_backslash_and_forward_slash_patterns_are_equivalent(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """dir1/dir2/ and dir1\\dir2\\ produce identical is_ignored results."""
        slash_base = tmp_path_factory.mktemp("slash_base")
        backslash_base = tmp_path_factory.mktemp("backslash_base")

        ig_slash = IgnoreFile(
            _write_ignore(slash_base, "dir1/dir2/\n"), base_dir=slash_base
        )
        ig_backslash = IgnoreFile(
            _write_ignore(backslash_base, "dir1\\dir2\\\n"), base_dir=backslash_base
        )

        slash_nested = _make_dir(slash_base, "dir1/dir2")
        backslash_nested = _make_dir(backslash_base, "dir1/dir2")

        assert ig_slash.is_ignored(slash_nested) == ig_backslash.is_ignored(
            backslash_nested
        )
        assert ig_backslash.is_ignored(backslash_nested) is True

    def test_backslash_multi_level_pattern_stays_anchored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dir1\\dir2\\ is anchored to base_dir and does not float like an unanchored pattern."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1\\dir2\\\n"))
        floating_nested = _make_dir(tmp_path, "a/dir1/dir2")
        assert ig.is_ignored(floating_nested) is False

    def test_backslash_multi_level_pattern_does_not_match_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dir1\\dir2\\ does NOT match a regular file named dir1/dir2 — no fallback."""
        monkeypatch.chdir(tmp_path)
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1\\dir2\\\n"))
        nested_file = _make_file(tmp_path, "dir1/dir2")
        assert ig.is_ignored(nested_file) is False


# ---------------------------------------------------------------------------
# TestIsAncestorIgnoredSeparators
# ---------------------------------------------------------------------------


class TestIsAncestorIgnoredSeparators:
    """Unit tests for _is_ancestor_ignored regarding \\ and / usage."""

    def test_true_when_ancestor_matches_forward_slash_pattern(
        self, tmp_path: Path
    ) -> None:
        """An ancestor directory matching a / pattern is detected as ignored."""
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1/dir2/\n"), base_dir=tmp_path)
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig._is_ancestor_ignored(nested_file.resolve()) is True

    def test_true_when_ancestor_matches_backslash_pattern(self, tmp_path: Path) -> None:
        """An ancestor directory matching a \\ pattern is detected as ignored."""
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1\\dir2\\\n"), base_dir=tmp_path)
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig._is_ancestor_ignored(nested_file.resolve()) is True

    def test_false_when_no_ancestor_matches(self, tmp_path: Path) -> None:
        """No ancestor matches an unrelated pattern, so the result is False."""
        ig = IgnoreFile(_write_ignore(tmp_path, "other/\n"), base_dir=tmp_path)
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig._is_ancestor_ignored(nested_file.resolve()) is False

    def test_false_when_only_the_path_itself_matches(self, tmp_path: Path) -> None:
        """A pattern matching the path itself (not an ancestor) does not count."""
        ig = IgnoreFile(_write_ignore(tmp_path, "file.txt\n"), base_dir=tmp_path)
        target_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig._is_ancestor_ignored(target_file.resolve()) is False

    def test_true_with_backslash_base_dir_string_and_forward_slash_pattern(
        self, tmp_path: Path
    ) -> None:
        """A \\-based base_dir string still detects an ancestor matched by a / pattern."""
        base_dir_str = str(tmp_path).replace("/", "\\")
        ig = IgnoreFile(_write_ignore(tmp_path, "dir1/dir2/\n"), base_dir=base_dir_str)
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig._is_ancestor_ignored(nested_file.resolve()) is True

    def test_true_with_forward_slash_base_dir_string_and_backslash_pattern(
        self, tmp_path: Path
    ) -> None:
        """A /-based base_dir string still detects an ancestor matched by a \\ pattern."""
        base_dir_str = str(tmp_path).replace("\\", "/")
        ig = IgnoreFile(
            _write_ignore(tmp_path, "dir1\\dir2\\\n"), base_dir=base_dir_str
        )
        nested_file = _make_file(tmp_path, "dir1/dir2/file.txt")
        assert ig._is_ancestor_ignored(nested_file.resolve()) is True

    def test_forward_and_backslash_patterns_give_identical_ancestor_result(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """/ and \\ patterns produce the same _is_ancestor_ignored outcome."""
        slash_base = tmp_path_factory.mktemp("ancestor_slash_base")
        backslash_base = tmp_path_factory.mktemp("ancestor_backslash_base")

        ig_slash = IgnoreFile(
            _write_ignore(slash_base, "dir1/dir2/\n"), base_dir=slash_base
        )
        ig_backslash = IgnoreFile(
            _write_ignore(backslash_base, "dir1\\dir2\\\n"), base_dir=backslash_base
        )

        slash_file = _make_file(slash_base, "dir1/dir2/file.txt")
        backslash_file = _make_file(backslash_base, "dir1/dir2/file.txt")

        assert ig_slash._is_ancestor_ignored(
            slash_file.resolve()
        ) == ig_backslash._is_ancestor_ignored(backslash_file.resolve())


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
# TestAncestorNegation
# ---------------------------------------------------------------------------


class TestAncestorNegation:
    """Tests that a directory-only negation cascades to its descendants."""

    def test_negated_subdirectory_re_includes_its_direct_contents(
        self, tmp_path: Path
    ) -> None:
        """!build/keep/ re-includes a file directly under the re-included dir."""
        ig = IgnoreFile(
            _write_ignore(tmp_path, "build/\n!build/keep/\n"), base_dir=tmp_path
        )
        assert ig.is_ignored(_make_file(tmp_path, "build/keep/file.txt")) is False

    def test_negated_subdirectory_re_includes_nested_descendants(
        self, tmp_path: Path
    ) -> None:
        """The re-inclusion also cascades to deeper descendants of that dir."""
        ig = IgnoreFile(
            _write_ignore(tmp_path, "build/\n!build/keep/\n"), base_dir=tmp_path
        )
        assert ig.is_ignored(_make_file(tmp_path, "build/keep/sub/file2.txt")) is False

    def test_sibling_of_negated_subdirectory_stays_ignored(
        self, tmp_path: Path
    ) -> None:
        """A sibling directory not covered by the negation remains ignored."""
        ig = IgnoreFile(
            _write_ignore(tmp_path, "build/\n!build/keep/\n"), base_dir=tmp_path
        )
        assert ig.is_ignored(_make_file(tmp_path, "build/file.txt")) is True

    def test_is_ancestor_ignored_false_for_negated_directory(
        self, tmp_path: Path
    ) -> None:
        """_is_ancestor_ignored stops at the nearest ancestor's own verdict."""
        ig = IgnoreFile(
            _write_ignore(tmp_path, "build/\n!build/keep/\n"), base_dir=tmp_path
        )
        nested = _make_file(tmp_path, "build/keep/file.txt")
        assert ig._is_ancestor_ignored(nested.resolve()) is False

    def test_is_ancestor_ignored_true_for_non_negated_ancestor(
        self, tmp_path: Path
    ) -> None:
        """A farther ignored ancestor is still detected when nothing nearer matches."""
        ig = IgnoreFile(
            _write_ignore(tmp_path, "build/\n!build/keep/\n"), base_dir=tmp_path
        )
        nested = _make_file(tmp_path, "build/other/file.txt")
        assert ig._is_ancestor_ignored(nested.resolve()) is True


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

    def test_base_dir_as_file_uses_parent_directory(self, tmp_path: Path) -> None:
        """When base_dir is a file, its parent directory is used instead."""
        base_file = _make_file(tmp_path, "somefile.txt")
        ig = IgnoreFile(_write_ignore(tmp_path, "/build\n"), base_dir=base_file)
        # anchored pattern should match relative to tmp_path (base_file's parent)
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


# ---------------------------------------------------------------------------
# TestIgnoreFileBaseDirAboveAnchoredAncestor
# ---------------------------------------------------------------------------


class TestIgnoreFileBaseDirAboveAnchoredAncestor:
    """Tests for anchored patterns whose matched ancestor sits above base_dir."""

    def test_base_dir_as_nested_file_still_matches_anchored_ancestor(
        self, tmp_path: Path, gosu_xyz_ignore_file: Path
    ) -> None:
        """base_dir set to a deeply nested file still ignores it via gosu/xyz/."""
        target_file = _make_file(tmp_path, "gosu/xyz/ronella/gosu/ginfuser/IInfuser.gs")
        ig = IgnoreFile(gosu_xyz_ignore_file, base_dir=target_file)
        assert ig.is_ignored(target_file) is True

    def test_is_ancestor_ignored_true_when_base_dir_nested_under_match(
        self, tmp_path: Path, gosu_xyz_ignore_file: Path
    ) -> None:
        """_is_ancestor_ignored detects the anchored ancestor above base_dir."""
        target_file = _make_file(tmp_path, "gosu/xyz/ronella/gosu/ginfuser/IInfuser.gs")
        ig = IgnoreFile(gosu_xyz_ignore_file, base_dir=target_file)
        assert ig._is_ancestor_ignored(target_file.resolve()) is True

    def test_sibling_directory_outside_pattern_tree_not_ignored(
        self, tmp_path: Path, gosu_xyz_ignore_file: Path
    ) -> None:
        """A file under a differently named ancestor is not affected."""
        target_file = _make_file(
            tmp_path, "gosu/other/ronella/gosu/ginfuser/IInfuser.gs"
        )
        ig = IgnoreFile(gosu_xyz_ignore_file, base_dir=target_file)
        assert ig.is_ignored(target_file) is False

    def test_disjoint_base_dir_still_requires_exact_anchor(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """An anchored pattern still does not match a fully unrelated base_dir tree."""
        other = tmp_path_factory.mktemp("disjoint_base")
        ig = IgnoreFile(_write_ignore(tmp_path, "/build\n"), base_dir=other)
        target = _make_file(tmp_path, "build")
        assert ig.is_ignored(target) is False
