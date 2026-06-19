# Changelog

## 1.0.0 - 2026-06-19

### Added

- Initial release of braincraft.
- Core package structure with `logenrich` logging integration.
- `retry` module: `retry_rand_exp` async helper with full-jitter exponential back-off.
- GitHub Actions CI workflow (`tests.yml`): lint (black, pylint) and pytest with 80% coverage gate on every push and pull request.
