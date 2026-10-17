"""Tests for NC1 parser."""

from plate_nesting.nc1.parser import parse_nc1

from .conftest import NC1_DIR


class TestParseNc1:
    def test_parse_simple_rect(self):
        text = (NC1_DIR / "6C-p5.nc1").read_text()
        part = parse_nc1(text)
        assert part.name == "6C-p5"
        assert part.grade == "350W"
        assert part.thickness == 50.0
        assert part.qty == 10
        assert part.order == "W8753"
        assert part.phase == "63"
        assert abs(part.length - 615.0) < 0.01
        assert abs(part.width - 350.0) < 0.01
        assert len(part.outer) == 4  # rectangle = 4 line segments
        assert len(part.inners) == 0
        assert len(part.holes) == 0

    def test_parse_with_arcs(self):
        text = (NC1_DIR / "6C-p13.nc1").read_text()
        part = parse_nc1(text)
        assert part.name == "6C-p13"
        assert part.qty == 28
        # Outer has 6 segments (some are arcs), inner has arcs
        assert len(part.outer) >= 4  # may have more due to arc splitting
        assert len(part.inners) == 1

    def test_parse_ring_with_holes(self):
        text = (NC1_DIR / "6C-p1.nc1").read_text()
        part = parse_nc1(text)
        assert part.name == "6C-p1"
        assert len(part.holes) == 16
        assert len(part.inners) == 1  # inner ring cutout
        # All holes should have diameter 24.23
        for _, _, d in part.holes:
            assert abs(d - 24.23) < 0.01

    def test_parse_no_thickness(self):
        """Parts with PL (no number) should have thickness 0."""
        # Construct a minimal NC1 with "PL" (no thickness)
        lines = [
            "ST",
            "** test.nc1",
            "  W8753",
            "  test",
            "  63",
            "  test",
            "  ",
            "  1",
            "  PL",
            "  B",
            "     100.00",
            "     100.00",
            "       0.00",
            "       0.00",
            "       0.00",
            "       0.00",
            "      0.000",
            "      0.000",
            "      0.000",
            "      0.000",
            "      0.000",
            "      0.000",
            "",
            "",
            "",
            "AK",
            "  v       0.00u      0.00       0.00"
            + "       0.00       0.00       0.00       0.00",
            "        100.00       0.00       0.00"
            + "       0.00       0.00       0.00       0.00",
            "        100.00     100.00       0.00"
            + "       0.00       0.00       0.00       0.00",
            "          0.00     100.00       0.00"
            + "       0.00       0.00       0.00       0.00",
            "          0.00       0.00       0.00"
            + "       0.00       0.00       0.00       0.00",
            "EN",
        ]
        text = "\r\n".join(lines) + "\r\n"
        part = parse_nc1(text)
        assert part.thickness == 0.0
