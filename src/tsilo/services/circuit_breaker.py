"""Circuit breaker for external dependencies - fail fast with 503 and Retry-After."""

import time
from enum import StrEnum
from threading import Lock


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple circuit breaker that opens after consecutive failures.

    When open, calls fail immediately with a known error instead of
    waiting for a timeout against an unresponsive service.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def retry_after(self) -> int:
        """Seconds until the circuit breaker will attempt recovery."""
        with self._lock:
            if self._state != CircuitState.OPEN:
                return 0
            elapsed = time.monotonic() - self._last_failure_time
            remaining = max(0, self._recovery_timeout - elapsed)
            return int(remaining) + 1

    def reset(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._last_failure_time = 0.0


# Shared circuit breakers for external dependencies
oidc_breaker = CircuitBreaker("oidc", failure_threshold=3, recovery_timeout=30.0)
s3_breaker = CircuitBreaker("s3", failure_threshold=3, recovery_timeout=30.0)
