import logging
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

log = logging.getLogger(__name__)


@pytest.fixture
def temporary_dir() -> Iterator[Path]:
    with TemporaryDirectory() as path:
        yield Path(path)
