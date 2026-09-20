from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar


Result = TypeVar("Result")


def retry_call(
    operation: Callable[[], Result],
    *,
    attempts: int,
    retry_on: tuple[type[BaseException], ...],
    on_retry: Callable[[int, int], None],
) -> Result:
    """Retry only the declared transient failures and preserve the last error."""
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retry_on:
            if attempt == attempts:
                raise
            on_retry(attempt + 1, attempts)
    raise AssertionError("unreachable retry state")
