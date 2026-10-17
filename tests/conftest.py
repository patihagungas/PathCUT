"""Shared test fixtures."""

from pathlib import Path

import pytest

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "plate-nesting" / "reference"
NC1_DIR = REFERENCE_DIR / "nc1"
DXF_DIR = REFERENCE_DIR / "dxf"


@pytest.fixture
def nc1_dir() -> Path:
    return NC1_DIR


@pytest.fixture
def dxf_dir() -> Path:
    return DXF_DIR


@pytest.fixture
def nc1_files() -> list[Path]:
    return sorted(NC1_DIR.glob("*.nc1"))


@pytest.fixture
def dxf_files() -> list[Path]:
    return sorted(DXF_DIR.glob("*.dxf"))
