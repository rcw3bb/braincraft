"""
braincraft.version_check - Check a package index for a newer version of an application.

Queries either a PyPI Warehouse-compatible JSON API (``/pypi/<app_name>/json``) or a
Nexus Repository 3 PEP 691 JSON Simple API (``/simple/<app_name>/``) to determine
whether a newer version of a given application/package is published. All failures
(network errors, missing package metadata, malformed responses) are logged and
treated as "no update information available" rather than raised, so callers can use
this as a best-effort, non-critical check.

:author: Ron Webb
:since: 1.3.0
"""

import json
import urllib.error
import urllib.request
from enum import Enum
from importlib import metadata

from logenrich import setup_logger

_logger = setup_logger(__name__)

_DEFAULT_INDEX_URL = "https://pypi.org"
_DEFAULT_TIMEOUT = 5.0
_NEXUS3_SIMPLE_ACCEPT = "application/vnd.pypi.simple.v1+json"


class IndexKind(Enum):
    """Kind of package index queried by :func:`check_new_version`.

    :cvar PYPI: A PyPI Warehouse-compatible JSON API (e.g. ``https://pypi.org``).
    :cvar NEXUS3: A Sonatype Nexus Repository 3 PyPI-format repository, queried via
        its PEP 691 JSON Simple API.
    """

    PYPI = "pypi"
    NEXUS3 = "nexus3"


def _parse_version(version: str) -> tuple[int, ...]:
    """Parses a dotted version string into a tuple of integers for comparison.

    Non-numeric segments (e.g. pre-release suffixes like ``1.3.0rc1``) are truncated
    to their leading digit run, or treated as ``0`` when no leading digits exist.

    :param version: Dotted version string, e.g. ``"1.3.0"``.
    :return: Tuple of integers, one per dotted segment.
    """
    parts: list[int] = []
    for segment in version.split("."):
        digits = ""
        for char in segment:
            if not char.isdigit():
                break
            digits += char
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_newer(current: str, latest: str) -> bool:
    """Determines whether *latest* is a newer version than *current*.

    :param current: Currently installed version string.
    :param latest: Version string reported by the index.
    :return: ``True`` if *latest* is greater than *current*, otherwise ``False``.
    """
    current_parts = _parse_version(current)
    latest_parts = _parse_version(latest)
    length = max(len(current_parts), len(latest_parts))
    current_parts += (0,) * (length - len(current_parts))
    latest_parts += (0,) * (length - len(latest_parts))
    return latest_parts > current_parts


def _fetch_pypi_version(app_name: str, index_url: str, timeout: float) -> str | None:
    """Fetches the latest version from a PyPI Warehouse-compatible JSON API.

    :param app_name: Package name as published on the index.
    :param index_url: Base URL of the PyPI Warehouse-compatible JSON API.
    :param timeout: Request timeout in seconds.
    :return: The latest version string, or ``None`` if it could not be determined.
    """
    url = f"{index_url.rstrip('/')}/pypi/{app_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.load(response)
        return data["info"]["version"]
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _logger.warning(
            "Could not fetch latest version for %r from %r: %s", app_name, url, exc
        )
        return None


def _fetch_nexus3_version(app_name: str, index_url: str, timeout: float) -> str | None:
    """Fetches the latest version from a Nexus 3 PEP 691 JSON Simple API.

    :param app_name: Package name as published on the index.
    :param index_url: Base URL of the Nexus 3 PyPI-format repository (up to and
        including the repository name, e.g. ``https://host/repository/pypi-hosted``).
    :param timeout: Request timeout in seconds.
    :return: The latest version string, or ``None`` if it could not be determined.
    """
    url = f"{index_url.rstrip('/')}/simple/{app_name}/"
    request = urllib.request.Request(url, headers={"Accept": _NEXUS3_SIMPLE_ACCEPT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        versions: list[str] = data["versions"]
        return max(versions, key=_parse_version) if versions else None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _logger.warning(
            "Could not fetch latest version for %r from %r: %s", app_name, url, exc
        )
        return None


def _fetch_latest_version(
    app_name: str, index_url: str, timeout: float, index_kind: IndexKind
) -> str | None:
    """Fetches the latest published version of *app_name* from *index_url*.

    :param app_name: Package name as published on the index.
    :param index_url: Base URL of the index.
    :param timeout: Request timeout in seconds.
    :param index_kind: Kind of index to query.
    :return: The latest version string, or ``None`` if it could not be determined.
    """
    if index_kind is IndexKind.NEXUS3:
        return _fetch_nexus3_version(app_name, index_url, timeout)
    return _fetch_pypi_version(app_name, index_url, timeout)


def check_new_version(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    app_name: str,
    current_version: str | None = None,
    index_url: str = _DEFAULT_INDEX_URL,
    disable: bool = False,
    timeout: float = _DEFAULT_TIMEOUT,
    index_kind: IndexKind = IndexKind.PYPI,
) -> str | None:
    """Checks whether a newer version of *app_name* is available on an index.

    :param app_name: Name of the application/package to check, as published on the index.
    :param current_version: Currently installed version. When ``None``, it is
        auto-detected via :func:`importlib.metadata.version`.
    :param index_url: Base URL of the index to query.
    :param disable: When ``True``, the check is skipped entirely.
    :param timeout: Request timeout in seconds.
    :param index_kind: Kind of index to query. Defaults to :attr:`IndexKind.PYPI`.
    :return: The latest version string if newer than *current_version*, otherwise ``None``.
    :raises: Never raises; failures are logged and reported as ``None``.
    """
    if disable:
        return None
    if current_version is None:
        try:
            current_version = metadata.version(app_name)
        except metadata.PackageNotFoundError as exc:
            _logger.warning(
                "Could not determine installed version of %r: %s", app_name, exc
            )
            return None
    latest_version = _fetch_latest_version(app_name, index_url, timeout, index_kind)
    if latest_version is None:
        return None
    return latest_version if _is_newer(current_version, latest_version) else None
