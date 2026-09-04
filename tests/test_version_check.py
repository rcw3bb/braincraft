"""
Tests for braincraft.version_check module.

:author: Ron Webb
:since: 1.3.0
"""

import json
import urllib.error
from importlib import metadata
from unittest.mock import MagicMock, patch

from braincraft.version_check import (
    IndexKind,
    _fetch_latest_version,
    _fetch_nexus3_version,
    _fetch_pypi_version,
    _is_newer,
    _parse_version,
    check_new_version,
)


class TestParseVersion:
    """Tests for :func:`braincraft.version_check._parse_version`."""

    def test_simple_dotted_version(self) -> None:
        """Parses a plain major.minor.patch version into an int tuple."""
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_pre_release_suffix_truncated(self) -> None:
        """Non-digit suffix on a segment is truncated to its leading digit run."""
        assert _parse_version("1.3.0rc1") == (1, 3, 0)

    def test_non_numeric_segment_becomes_zero(self) -> None:
        """A segment with no leading digits becomes 0."""
        assert _parse_version("1.dev.0") == (1, 0, 0)


class TestIsNewer:
    """Tests for :func:`braincraft.version_check._is_newer`."""

    def test_returns_true_when_latest_greater(self) -> None:
        """Detects a strictly greater latest version."""
        assert _is_newer("1.2.0", "1.3.0") is True

    def test_returns_false_when_equal(self) -> None:
        """Equal versions are not considered newer."""
        assert _is_newer("1.2.0", "1.2.0") is False

    def test_returns_false_when_latest_older(self) -> None:
        """A latest version older than current is not considered newer."""
        assert _is_newer("1.3.0", "1.2.0") is False

    def test_handles_different_segment_lengths(self) -> None:
        """Shorter version tuples are zero-padded before comparison."""
        assert _is_newer("1.2", "1.2.1") is True


class TestFetchPypiVersion:
    """Tests for :func:`braincraft.version_check._fetch_pypi_version`."""

    def test_returns_version_on_success(self) -> None:
        """Returns the version reported in the JSON response's info.version field."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={"info": {"version": "1.5.0"}}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = _fetch_pypi_version("braincraft", "https://pypi.org", 5.0)
        assert result == "1.5.0"

    def test_builds_url_from_index_and_app_name(self) -> None:
        """Request URL is built from the index_url and app_name."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={"info": {"version": "1.0.0"}}):
            with patch(
                "urllib.request.urlopen", return_value=mock_response
            ) as mock_urlopen:
                _fetch_pypi_version("braincraft", "https://test.pypi.org/", 5.0)
        mock_urlopen.assert_called_once()
        called_url = mock_urlopen.call_args[0][0]
        assert called_url == "https://test.pypi.org/pypi/braincraft/json"

    def test_returns_none_on_url_error(self) -> None:
        """Network errors are caught and reported as None."""
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("unreachable"),
        ):
            result = _fetch_pypi_version("braincraft", "https://pypi.org", 5.0)
        assert result is None

    def test_returns_none_on_malformed_json(self) -> None:
        """A malformed response (missing keys) is caught and reported as None."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = _fetch_pypi_version("braincraft", "https://pypi.org", 5.0)
        assert result is None


class TestFetchNexus3Version:
    """Tests for :func:`braincraft.version_check._fetch_nexus3_version`."""

    def test_returns_highest_version_on_success(self) -> None:
        """Returns the highest version reported in the Simple API's versions list."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={"versions": ["1.0.0", "1.5.0", "1.2.0"]}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = _fetch_nexus3_version(
                    "braincraft", "https://nexus.example.com/repository/pypi", 5.0
                )
        assert result == "1.5.0"

    def test_builds_url_and_accept_header(self) -> None:
        """Request URL and Accept header target the PEP 691 JSON Simple API."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={"versions": ["1.0.0"]}):
            with patch(
                "urllib.request.urlopen", return_value=mock_response
            ) as mock_urlopen:
                _fetch_nexus3_version(
                    "braincraft", "https://nexus.example.com/repository/pypi/", 5.0
                )
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        assert (
            request.full_url
            == "https://nexus.example.com/repository/pypi/simple/braincraft/"
        )
        assert request.get_header("Accept") == "application/vnd.pypi.simple.v1+json"

    def test_returns_none_on_empty_versions(self) -> None:
        """An empty versions list is treated as no data available."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={"versions": []}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = _fetch_nexus3_version(
                    "braincraft", "https://nexus.example.com/repository/pypi", 5.0
                )
        assert result is None

    def test_returns_none_on_url_error(self) -> None:
        """Network errors are caught and reported as None."""
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("unreachable"),
        ):
            result = _fetch_nexus3_version(
                "braincraft", "https://nexus.example.com/repository/pypi", 5.0
            )
        assert result is None

    def test_returns_none_on_malformed_json(self) -> None:
        """A malformed response (missing versions key) is caught and reported as None."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = MagicMock()
        with patch("json.load", return_value={}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = _fetch_nexus3_version(
                    "braincraft", "https://nexus.example.com/repository/pypi", 5.0
                )
        assert result is None


class TestFetchLatestVersion:
    """Tests for :func:`braincraft.version_check._fetch_latest_version` dispatch."""

    def test_dispatches_to_pypi_fetcher(self) -> None:
        """IndexKind.PYPI dispatches to the PyPI fetcher."""
        with patch(
            "braincraft.version_check._fetch_pypi_version", return_value="1.0.0"
        ) as mock_fetch:
            result = _fetch_latest_version(
                "braincraft", "https://pypi.org", 5.0, IndexKind.PYPI
            )
        mock_fetch.assert_called_once_with("braincraft", "https://pypi.org", 5.0)
        assert result == "1.0.0"

    def test_dispatches_to_nexus3_fetcher(self) -> None:
        """IndexKind.NEXUS3 dispatches to the Nexus 3 fetcher."""
        with patch(
            "braincraft.version_check._fetch_nexus3_version", return_value="1.0.0"
        ) as mock_fetch:
            result = _fetch_latest_version(
                "braincraft",
                "https://nexus.example.com/repository/pypi",
                5.0,
                IndexKind.NEXUS3,
            )
        mock_fetch.assert_called_once_with(
            "braincraft", "https://nexus.example.com/repository/pypi", 5.0
        )
        assert result == "1.0.0"


class TestCheckNewVersion:
    """Tests for :func:`braincraft.version_check.check_new_version`."""

    def test_disabled_returns_none_without_network_call(self) -> None:
        """When disable=True, no network call is made and None is returned."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            result = check_new_version("braincraft", disable=True)
        assert result is None
        mock_urlopen.assert_not_called()

    def test_explicit_current_version_skips_auto_detect(self) -> None:
        """An explicit current_version bypasses importlib.metadata lookup."""
        with patch(
            "braincraft.version_check._fetch_latest_version", return_value="2.0.0"
        ):
            with patch("importlib.metadata.version") as mock_version:
                result = check_new_version("braincraft", current_version="1.0.0")
        mock_version.assert_not_called()
        assert result == "2.0.0"

    def test_returns_latest_when_newer_available(self) -> None:
        """Returns the latest version string when it is newer than current."""
        with patch("importlib.metadata.version", return_value="1.0.0"):
            with patch(
                "braincraft.version_check._fetch_latest_version",
                return_value="1.1.0",
            ):
                result = check_new_version("braincraft")
        assert result == "1.1.0"

    def test_returns_none_when_up_to_date(self) -> None:
        """Returns None when the current version is already the latest."""
        with patch("importlib.metadata.version", return_value="1.1.0"):
            with patch(
                "braincraft.version_check._fetch_latest_version",
                return_value="1.1.0",
            ):
                result = check_new_version("braincraft")
        assert result is None

    def test_returns_none_when_fetch_fails(self) -> None:
        """Returns None when the latest version could not be fetched."""
        with patch("importlib.metadata.version", return_value="1.0.0"):
            with patch(
                "braincraft.version_check._fetch_latest_version", return_value=None
            ):
                result = check_new_version("braincraft")
        assert result is None

    def test_returns_none_when_package_not_found(self) -> None:
        """Returns None when auto-detecting current_version raises PackageNotFoundError."""
        with patch(
            "importlib.metadata.version",
            side_effect=metadata.PackageNotFoundError("not found"),
        ):
            result = check_new_version("unknown-app")
        assert result is None

    def test_custom_index_url_is_forwarded(self) -> None:
        """A custom index_url is forwarded to the fetch helper."""
        with patch("importlib.metadata.version", return_value="1.0.0"):
            with patch(
                "braincraft.version_check._fetch_latest_version", return_value=None
            ) as mock_fetch:
                check_new_version("braincraft", index_url="https://test.pypi.org")
        mock_fetch.assert_called_once_with(
            "braincraft", "https://test.pypi.org", 5.0, IndexKind.PYPI
        )

    def test_custom_timeout_is_forwarded(self) -> None:
        """A custom timeout is forwarded to the fetch helper."""
        with patch("importlib.metadata.version", return_value="1.0.0"):
            with patch(
                "braincraft.version_check._fetch_latest_version", return_value=None
            ) as mock_fetch:
                check_new_version("braincraft", timeout=10.0)
        mock_fetch.assert_called_once_with(
            "braincraft", "https://pypi.org", 10.0, IndexKind.PYPI
        )

    def test_custom_index_kind_is_forwarded(self) -> None:
        """A custom index_kind is forwarded to the fetch helper."""
        with patch("importlib.metadata.version", return_value="1.0.0"):
            with patch(
                "braincraft.version_check._fetch_latest_version", return_value=None
            ) as mock_fetch:
                check_new_version(
                    "braincraft",
                    index_url="https://nexus.example.com/repository/pypi",
                    index_kind=IndexKind.NEXUS3,
                )
        mock_fetch.assert_called_once_with(
            "braincraft",
            "https://nexus.example.com/repository/pypi",
            5.0,
            IndexKind.NEXUS3,
        )
