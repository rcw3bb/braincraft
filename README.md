# braincraft

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)](CHANGELOG.md)

> A workshop of small, sharp utilities — carefully shaped helpers you reuse across projects to keep everyday coding tasks fast, tidy, and consistent.

## Prerequisites

- Python `>=3.14`

## Installation

Install via pip:

```bash
pip install braincraft
```

Or add it as a Poetry dependency:

```bash
poetry add braincraft
```

## Components

```mermaid
graph TD
    A[braincraft] --> B[ignorefile]
    A --> C[retry]
    A --> D[version_check]
    B --> B1["IgnoreFile — gitignore-style path matching"]
    B --> B2["PatternHandler — extensible custom pattern handlers"]
    C --> C1["retry_rand_exp — async retry with full-jitter back-off"]
    D --> D1["check_new_version — checks an index for a newer app/package version"]
    D --> D2["IndexKind — PYPI or NEXUS3 index selector"]
```

| Module | Exported symbols | Purpose |
|---|---|---|
| `ignorefile` | `IgnoreFile`, `PatternHandler` | Gitignore-style ignore-file parsing with extensible handlers |
| `retry` | `retry_rand_exp` | Async retry with full-jitter exponential back-off |
| `version_check` | `check_new_version`, `IndexKind` | Checks a PyPI or Nexus 3 index for a newer version of an app/package |

## Usage

### `IgnoreFile`

Reads a gitignore-style ignore file and determines whether a given path should be
ignored. Pattern matching follows the full [gitignore specification](https://git-scm.com/docs/gitignore):
`*`, `?`, `[...]` wildcards, negation (`!`), directory-only patterns (trailing `/`),
`**` double-star rules, and anchoring.

Anchored patterns (containing `/` at the start or middle, e.g. `doc/build` or
`/dist`) are matched relative to a **base directory** — by default the current
working directory at the time `IgnoreFile` is created. An explicit `base_dir`
(`str | Path`) can be supplied to override this. The ignore file can live anywhere,
independently of `base_dir`.

Matching always occurs — no error is raised for paths outside the base directory.

```python
from pathlib import Path
from braincraft import IgnoreFile

ig = IgnoreFile(Path(".gitignore"))

print(ig.is_ignored(Path("dist/output.js")))       # True
print(ig.is_ignored(Path("src/main.py")))          # False
print(ig.is_ignored(Path("build/")))               # True (if build/ is a directory)
```

#### Custom base directory

By default `IgnoreFile` uses the current working directory as the root for anchored
patterns. Pass `base_dir` (`str` or `Path`) to pin matching to a specific directory
regardless of where the process is running or where the ignore file lives.

```python
from pathlib import Path
from braincraft import IgnoreFile

project = Path("/srv/myproject")
ig = IgnoreFile(project / ".gitignore", base_dir=project)

# Anchored pattern /dist matches relative to project, not the process CWD
print(ig.is_ignored(project / "dist" / "bundle.js"))   # True
print(ig.is_ignored(project / "src" / "main.py"))      # False

# Works equally well with plain strings
ig2 = IgnoreFile("/srv/myproject/.gitignore", base_dir="/srv/myproject")
print(ig2.is_ignored("/srv/myproject/dist/bundle.js"))  # True
```

#### Custom pattern handlers

Extend matching behaviour by registering a `PatternHandler` subclass. Custom handlers
are consulted first; returning `None` falls through to the built-in gitignore handler.

```python
from pathlib import Path
from braincraft import IgnoreFile, PatternHandler


class SizePatternHandler(PatternHandler):
    """Ignore files larger than a size encoded as 'size:>NNN' in the ignore file."""

    def matches(self, pattern: str, path: Path, base_dir: Path) -> bool | None:
        if not pattern.startswith("size:>"):
            return None  # not our pattern — let the built-in handle it
        limit = int(pattern.removeprefix("size:>"))
        if path.is_file():
            return path.stat().st_size > limit
        return None


ig = IgnoreFile(Path(".myignore"))
ig.register_handler(SizePatternHandler())

print(ig.is_ignored(Path("huge_dump.bin")))  # True if file > limit
```

### `retry_rand_exp`

Calls an async coroutine with automatic retry and full-jitter exponential back-off.
Retries on any exception up to `max_attempts` times, sleeping a random jittered
duration between attempts. Re-raises the last exception when all attempts are exhausted.

```python
from braincraft import retry_rand_exp

async def fetch_data(url: str) -> str:
    # your async operation here
    ...

result = await retry_rand_exp(
    fetch_data,
    "https://example.com/api",
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
)
```

### `check_new_version`

Checks a package index for a newer version of a given application/package. The
currently installed version is auto-detected via `importlib.metadata` when not
supplied explicitly. Never raises — network errors, missing metadata, or malformed
responses are logged and reported as "no update available" (`None`).

```python
from braincraft import check_new_version

latest = check_new_version("braincraft")
if latest is not None:
    print(f"A newer version is available: {latest}")
```

Optional parameters:

- `current_version` — override the auto-detected installed version.
- `index_url` — base URL of the index to query (default `https://pypi.org`).
- `disable` — skip the check entirely and return `None` immediately.
- `timeout` — request timeout in seconds (default `5`).
- `index_kind` — an `IndexKind` enum selecting the index API to query:
  - `IndexKind.PYPI` (default) — a PyPI Warehouse-compatible JSON API.
  - `IndexKind.NEXUS3` — a Sonatype Nexus Repository 3 PyPI-format repository,
    queried via its PEP 691 JSON Simple API.

```python
from braincraft import IndexKind, check_new_version

latest = check_new_version(
    "my-internal-package",
    index_url="https://nexus.example.com/repository/pypi-hosted",
    index_kind=IndexKind.NEXUS3,
)
```

## Development

### Prerequisites

- [Poetry](https://python-poetry.org/) `2.2+`

### Install dependencies

```bash
poetry install
```

### Format and lint

```bash
poetry run black braincraft; poetry run pylint braincraft
```

### Run tests with coverage

```bash
poetry run pytest --cov=braincraft tests --cov-report html
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of changes.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Author

Ron Webb
