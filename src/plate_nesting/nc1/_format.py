"""Shared constants and formatting helpers for NC1 I/O."""

DENSITY = 7.85e-6  # kg/mm^3 (steel)


def f(v: float, w: int = 11, d: int = 2) -> str:
    """Format a float for NC1 output."""
    return f"{v:{w}.{d}f}"
