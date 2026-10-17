"""Nesting engines and utilities."""

from __future__ import annotations

from plate_nesting.models.layout import Layout
from plate_nesting.models.nesting import EngineType, NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet


def nest(
    parts: list[Part],
    sheets: list[Sheet],
    options: NestOptions | None = None,
) -> list[Layout]:
    """Nest parts onto sheets using the engine specified in options.

    Args:
        parts: Parts to nest (qty field is respected).
        sheets: Available sheet sizes.
        options: Nesting options. Defaults to TrueShape engine.

    Returns:
        One Layout per sheet used.
    """
    if options is None:
        options = NestOptions()

    if options.engine == EngineType.MAXRECTS:
        from plate_nesting.nesting.maxrects import MaxRectsEngine

        engine = MaxRectsEngine()
    else:
        from plate_nesting.nesting.trueshape import TrueShapeEngine

        engine = TrueShapeEngine(time_budget=options.time_budget)

    return engine.nest(parts, sheets, options)
