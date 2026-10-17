"""Sheet model for nesting targets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GrainDirection(Enum):
    """Rolling / grain direction of a steel sheet."""

    NONE = "none"  # no grain constraint
    LENGTH = "length"  # grain runs along sheet length
    WIDTH = "width"  # grain runs along sheet width


@dataclass
class Sheet:
    """A rectangular steel sheet that parts are nested onto."""

    length: float
    width: float
    grade: str = ""
    thickness: float = 0.0
    label: str = ""
    grain: GrainDirection = GrainDirection.NONE

    @property
    def area(self) -> float:
        return self.length * self.width

    @property
    def weight(self) -> float:
        """Sheet weight in kg."""
        return self.thickness * 7.85e-6 * self.area
