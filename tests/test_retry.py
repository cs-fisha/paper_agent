"""Tests for retry utilities."""

import pytest
import time
from core.retry import retry_on_exception


class TestRetryOnException:
    """Test retry decorator."""

    def test_success_on_first_attempt(self):
        """Test function that succeeds on first attempt."""
        call_count = 0

        @retry_on_exception(max_attempts=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_success_after_retries(self):
        """Test function that succeeds after retries."""
        call_count = 0

        @retry_on_exception(max_attempts=3, delay=0.1)
        def eventually_successful_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = eventually_successful_func()
        assert result == "success"
        assert call_count == 3

    def test_failure_after_max_attempts(self):
        """Test function that fails after max attempts."""
        call_count = 0

        @retry_on_exception(max_attempts=3, delay=0.1)
        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_failing_func()

        assert call_count == 3

    def test_specific_exception_types(self):
        """Test retry only on specific exception types."""
        call_count = 0

        @retry_on_exception(max_attempts=3, delay=0.1, exceptions=(ValueError,))
        def specific_exception_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retry this")
            raise TypeError("Don't retry this")

        with pytest.raises(TypeError, match="Don't retry this"):
            specific_exception_func()

        assert call_count == 2  # First ValueError, then TypeError

    def test_exponential_backoff(self):
        """Test exponential backoff timing."""
        call_times = []

        @retry_on_exception(max_attempts=3, delay=0.1, backoff=2.0)
        def timed_func():
            call_times.append(time.time())
            raise ValueError("Test")

        with pytest.raises(ValueError):
            timed_func()

        assert len(call_times) == 3

        # Check delays are approximately correct (with some tolerance)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        assert 0.08 < delay1 < 0.15  # ~0.1s
        assert 0.18 < delay2 < 0.25  # ~0.2s (0.1 * 2.0)

    def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        retry_info = []

        def on_retry_callback(exception, attempt):
            retry_info.append((str(exception), attempt))

        @retry_on_exception(max_attempts=3, delay=0.1, on_retry=on_retry_callback)
        def callback_func():
            if len(retry_info) < 2:
                raise ValueError(f"Attempt {len(retry_info) + 1}")
            return "success"

        result = callback_func()
        assert result == "success"
        assert len(retry_info) == 2
        assert retry_info[0] == ("Attempt 1", 1)
        assert retry_info[1] == ("Attempt 2", 2)
