# Changelog

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
