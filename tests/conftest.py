from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_dir(name: str) -> list[tuple[str, str]]:
    d = FIXTURES / name
    return [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(d.glob("*.txt"))]


@pytest.fixture
def unlabeled_files() -> list[tuple[str, str]]:
    return load_dir("skiley_unlabeled")
