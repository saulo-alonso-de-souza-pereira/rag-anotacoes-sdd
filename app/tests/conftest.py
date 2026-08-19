from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock(fixed_now: datetime) -> Callable[[], datetime]:
    return lambda: fixed_now


@pytest.fixture
def uuid_sequence() -> Iterator[UUID]:
    values = (UUID(int=index) for index in range(1, 1_000))
    return values
