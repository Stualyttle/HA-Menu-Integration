from __future__ import annotations

import pytest
from io_fakes import Store


@pytest.fixture
def store() -> Store:
    return Store()
