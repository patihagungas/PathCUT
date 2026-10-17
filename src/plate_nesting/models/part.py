"""Central Part model used by all I/O modules."""

from __future__ import annotations

from dataclasses import dataclass, field

from plate_nesting.geometry.seg import Seg


@dataclass
class Part:
    """A flat steel plate part with contours and holes."""

    name: str
    outer: list[Seg] = field(default_factory=list)
    inners: list[list[Seg]] = field(default_factory=list)
    holes: list[tuple[float, float, float]] = field(default_factory=list)
    grade: str = ""
    thickness: float = 0.0
    qty: int = 1
    order: str = "W8753"
    phase: str = "63"
    length: float = 0.0
    width: float = 0.0
