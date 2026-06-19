"""
Tests for braincraft.retry module.

:author: Ron Webb
:since: 1.0.0
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from braincraft.retry import _compute_delay, retry_rand_exp


class TestComputeDelay:
    """Tests for :func:`braincraft.retry._compute_delay`."""

    def test_returns_zero_to_ceiling(self) -> None:
        """Result is within [0, min(max_delay, base_delay * 2^attempt)]."""
        for attempt in range(5):
            result = _compute_delay(attempt, base_delay=1.0, max_delay=30.0)
            ceiling = min(30.0, 1.0 * (2**attempt))
            assert 0.0 <= result <= ceiling

    def test_max_delay_caps_ceiling(self) -> None:
        """max_delay prevents the ceiling from exceeding its value."""
        for _ in range(20):
            result = _compute_delay(10, base_delay=1.0, max_delay=5.0)
            assert 0.0 <= result <= 5.0

    def test_attempt_zero_ceiling(self) -> None:
        """Attempt 0 ceiling equals base_delay * 1."""
        for _ in range(20):
            result = _compute_delay(0, base_delay=2.0, max_delay=100.0)
            assert 0.0 <= result <= 2.0

    def test_returns_float(self) -> None:
        """Return type is always float."""
        assert isinstance(_compute_delay(0, base_delay=1.0, max_delay=10.0), float)


class TestRetryAsync:
    """Tests for :func:`braincraft.retry.retry_async`."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        """Returns result immediately when func succeeds on first call."""
        mock_func = AsyncMock(return_value=42)
        result = await retry_rand_exp(
            mock_func, max_attempts=3, base_delay=0.0, max_delay=0.0
        )
        assert result == 42
        mock_func.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self) -> None:
        """Retries until success and returns the successful result."""
        mock_func = AsyncMock(
            side_effect=[RuntimeError("fail"), RuntimeError("fail"), "ok"]
        )
        with (
            patch("braincraft.retry._compute_delay", return_value=0.0),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await retry_rand_exp(
                mock_func, max_attempts=3, base_delay=0.0, max_delay=0.0
            )
        assert result == "ok"
        assert mock_func.await_count == 3

    @pytest.mark.asyncio
    async def test_raises_last_exception_after_all_attempts(self) -> None:
        """Re-raises the last exception when all attempts are exhausted."""
        exc = ValueError("all fail")
        mock_func = AsyncMock(side_effect=exc)
        with (
            patch("braincraft.retry._compute_delay", return_value=0.0),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(ValueError, match="all fail"):
                await retry_rand_exp(
                    mock_func, max_attempts=3, base_delay=0.0, max_delay=0.0
                )
        assert mock_func.await_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_one_no_retry(self) -> None:
        """With max_attempts=1, raises immediately without sleeping."""
        mock_func = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError, match="boom"):
                await retry_rand_exp(
                    mock_func, max_attempts=1, base_delay=1.0, max_delay=10.0
                )
        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_max_attempts_raises_value_error(self) -> None:
        """max_attempts < 1 raises ValueError before any call."""
        mock_func = AsyncMock()
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            await retry_rand_exp(mock_func, max_attempts=0, base_delay=1.0, max_delay=10.0)
        mock_func.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forwards_positional_and_keyword_args(self) -> None:
        """Passes *args and **kwargs through to the wrapped function."""

        async def capture(*args: object, **kwargs: object) -> tuple:
            return (args, kwargs)

        result = await retry_rand_exp(
            capture, 1, 2, max_attempts=1, base_delay=0.0, max_delay=0.0, key="val"
        )
        assert result == ((1, 2), {"key": "val"})

    @pytest.mark.asyncio
    async def test_sleep_called_between_retries(self) -> None:
        """asyncio.sleep is awaited once between two attempts."""
        mock_func = AsyncMock(side_effect=[RuntimeError("fail"), "done"])
        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("braincraft.retry._compute_delay", return_value=0.5),
        ):
            await retry_rand_exp(mock_func, max_attempts=2, base_delay=1.0, max_delay=10.0)
        mock_sleep.assert_awaited_once_with(0.5)
