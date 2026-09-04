# Changelog

## 1.3.0 - 2026-09-04

### Added

- `version_check` module: `check_new_version` function that checks a PyPI-compatible
  index (default `https://pypi.org`) for a newer version of a given application/package.
  Accepts a required `app_name`, an optional `current_version` (auto-detected via
  `importlib.metadata` when omitted), an optional `index_url` override, an optional
  `disable` flag, an optional `timeout` in seconds (default `5`), and an optional
  `index_kind` (`IndexKind` enum: `PYPI` or `NEXUS3`) selecting between a PyPI
  Warehouse-compatible JSON API and a Sonatype Nexus Repository 3 PEP 691 JSON Simple
  API. Never raises; failures are logged and reported as no update available.

## 1.2.0 - 2026-07-09

### Changed

- `IgnoreFile.__init__` now accepts an optional `base_dir` parameter (`str | Path | None`,
  default `None`). When supplied, it overrides the working directory used for
  anchored-pattern matching; when `None` the behaviour is unchanged (current working
  directory at construction time).

## 1.1.0 - 2026-07-06

### Added

- `ignorefile` module: `IgnoreFile` class that reads a gitignore-style ignore file and
  determines whether a given `Path` should be ignored, following the full gitignore
  pattern specification (`*`, `?`, `[...]`, `**`, negation `!`, directory-only `/`,
  anchoring, trailing-space handling, and comment lines).
- `PatternHandler` abstract base class for registering custom pattern handlers beyond
  the built-in gitignore rules; custom handlers are consulted first and return
  `True`/`False`/`None` (fall-through).

## 1.0.0 - 2026-06-19

### Added

- Initial release of braincraft.
- Core package structure with `logenrich` logging integration.
- `retry` module: `retry_rand_exp` async helper with full-jitter exponential back-off.
- GitHub Actions CI workflow (`tests.yml`): lint (black, pylint) and pytest with 80% coverage gate on every push and pull request.
