"""Nesting options and engine protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from plate_nesting.models.layout import Layout
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet


class EngineType(Enum):
    """Available nesting engine types."""

    MAXRECTS = "maxrects"
    TRUESHAPE = "trueshape"


@dataclass
class NestOptions:
    """Options controlling the nesting process."""

    engine: EngineType = EngineType.TRUESHAPE
    spacing: float = 10.0  # mm between parts (kerf + clearance)
    edge_margin: float = 10.0  # mm from sheet edge
    rotation_step: float = 90.0  # degrees (0 = no rotation, 90 = 4 orientations)
    allow_mirror: bool = False
    seed: int = 42  # for deterministic runs
    time_budget: int = 30  # seconds for true-shape solver

    # Common cuts
    common_cuts: bool = True  # detect shared edges between neighboring parts
    common_cut_max_thickness: float = 30.0  # skip detection above this (mm)

    # Part priorities: higher = placed first. Key = part name.
    priorities: dict[str, int] = field(default_factory=dict)


class NestingEngine(Protocol):
    """Protocol for nesting engines. Engines are swappable."""

    def nest(
        self,
        parts: list[Part],
        sheets: list[Sheet],
        options: NestOptions,
    ) -> list[Layout]:
        """Nest parts onto sheets. Returns one Layout per sheet used."""
        ...
