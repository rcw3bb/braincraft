# braincraft

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](CHANGELOG.md)

A workshop of small, sharp utilities - carefully shaped helpers you reuse across projects to keep everyday coding tasks fast, tidy, and consistent.

## Requirements

- Python `>=3.14`

## Usage

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
