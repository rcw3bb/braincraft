"""
braincraft.retry - Retry utilities with exponential back-off and full jitter.

Provides a generic async retry helper and a function that computes the next
sleep interval using the "Full Jitter" algorithm described in the AWS
Architecture Blog (exponential back-off + full random jitter).

:author: Ron Webb
:since: 1.0.0
"""

import asyncio
import random
from collections.abc import Callable, Coroutine
from typing import Any

from logenrich import setup_logger

_logger = setup_logger(__name__)


def _compute_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Computes the next sleep interval using full-jitter exponential back-off.

    The formula is: ``random.uniform(0, min(max_delay, base_delay * 2 ** attempt))``.

    :param attempt: Zero-based attempt index (0 = first retry).
    :param base_delay: Initial delay in seconds before jitter is applied.
    :param max_delay: Upper cap in seconds for the computed sleep interval.
    :return: A non-negative float representing the number of seconds to sleep.
    """
    ceiling = min(max_delay, base_delay * (2**attempt))
    return random.uniform(0, ceiling)


async def retry_rand_exp[T](  # pylint: disable=invalid-name
    func: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
    **kwargs: Any,
) -> T:
    """Calls an async coroutine function with retry and exponential-jitter back-off.

    Retries on any :class:`Exception` up to *max_attempts* times.  After each
    failure the caller sleeps for a jittered duration before the next attempt.
    If all attempts are exhausted the last exception is re-raised.

    :param func: Async callable to invoke.
    :param args: Positional arguments forwarded to *func*.
    :param max_attempts: Total number of attempts (must be >= 1).
    :param base_delay: Base delay in seconds used for back-off calculation.
    :param max_delay: Maximum sleep duration cap in seconds.
    :param kwargs: Keyword arguments forwarded to *func*.
    :return: The return value of a successful *func* invocation.
    :raises ValueError: If *max_attempts* is less than 1.
    :raises Exception: Re-raises the last exception when all attempts fail.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = _compute_delay(attempt, base_delay, max_delay)
                _logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.2fs.",
                    attempt + 1,
                    max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                _logger.error(
                    "Attempt %d/%d failed (%s). No more retries.",
                    attempt + 1,
                    max_attempts,
                    exc,
                )
    assert last_exc is not None  # guaranteed when max_attempts >= 1
    raise last_exc
