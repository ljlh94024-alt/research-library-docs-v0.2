from collections.abc import Iterator

import pytest

from research_library.storage import SQLiteRepository


@pytest.fixture
def repository(tmp_path) -> Iterator[SQLiteRepository]:
    with SQLiteRepository(tmp_path / "test.sqlite", tmp_path / "snapshots") as repo:
        yield repo
