## Purpose

braincraft is a Python utility library — a workshop of small, sharp helpers reused across projects to keep everyday coding tasks fast, tidy, and consistent. It is managed with Poetry 2.2+ (PEP 621) and requires Python >=3.14. Logging is provided by `logenrich`.

- Install: `poetry install`
- Format + lint: `poetry run black braincraft; poetry run pylint braincraft`
- Test with coverage: `poetry run pytest --cov=braincraft tests --cov-report html`

## Tree

- logging.ini — logging config (log file: braincraft.log); developer config at project root, not bundled
- braincraft/ — main package source code
- braincraft/__init__.py — package entry point: version, env bootstrap, logger setup
- tests/ — pytest test suite, mirrors braincraft/ structure
- pyproject.toml — PEP 621 project config + Poetry settings + dev dependency groups
- .pylintrc — Pylint config (must maintain 10/10 score)
- .gitignore — excludes .venv, *.log, .env, caches; poetry.lock is tracked
- .gitattributes — enforces LF line endings for all non-Windows files
- CHANGELOG.md — Keep a Changelog format
- README.md — project overview with license and version badges
- LICENSE — MIT license

## Rules

- Before adding a new module, place it in `braincraft/` and create a mirroring test file in `tests/` named `test_<module>.py`.
- Before bumping the version, update `__version__` in `braincraft/__init__.py` and add a CHANGELOG.md entry.
- Never modify `pyproject.toml` dependency constraints without running `poetry update` afterwards.
- Always run `poetry run pylint braincraft` after any code change — the linter must score 10/10.
- Always add docstrings to every module, class, and method. Include `:author: Ron Webb` and `:since: <version>` in every module docstring.
- Use type hints on all method arguments and return values. Use `collections.abc` instead of deprecated `typing` types.
- Use snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants. Prefix private/protected members with `_`.
- Follow SOLID, DRY, and composition-over-inheritance principles.
- Use `from logenrich import setup_logger` for logging — never configure the standard `logging` module directly.
- Never commit `.env` files or `*.log` files (enforced by .gitignore).
- Maintain minimum 80% test coverage. Never lower coverage without explicit approval.
- Never modify `poetry.lock`, `.pylintrc`, or `.gitattributes` without approval.
- When you create or discover new files, update the Tree above.

## Note-taking

- After each task, log any correction, preference, or pattern learned.
- Write to the matching context file's "Session learnings" section; if none fits, add to Rules above. One dated line, plain language.
  e.g. "Always wrap EnvDirBootstrap calls in a try/except for missing config (learned 2026-06-19)"
- 3+ related notes on the same topic → create a new `docs/` context file, move notes there, update the Tree. Keep this file under 100 lines.
