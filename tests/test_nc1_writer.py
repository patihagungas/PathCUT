"""Tests for NC1 writer."""

from plate_nesting.geometry.seg import Seg
from plate_nesting.models.part import Part
from plate_nesting.nc1.writer import write_nc1


class TestWriteNc1:
    def test_simple_square(self):
        part = Part(
            name="test",
            outer=[
                Seg((0, 0), (100, 0)),
                Seg((100, 0), (100, 100)),
                Seg((100, 100), (0, 100)),
                Seg((0, 100), (0, 0)),
            ],
            thickness=10.0,
            grade="S355",
            qty=2,
            length=100.0,
            width=100.0,
        )
        text = write_nc1(part)
        assert text.startswith("ST\n")
        assert "** test.nc1" in text
        assert "S355" in text
        assert "  2\n" in text  # qty
        assert "PL10" in text
        assert text.endswith("EN\n")

    def test_header_format(self):
        part = Part(
            name="mypart",
            outer=[
                Seg((0, 0), (200, 0)),
                Seg((200, 0), (200, 150)),
                Seg((200, 150), (0, 150)),
                Seg((0, 150), (0, 0)),
            ],
            thickness=25.0,
            grade="350W",
            qty=5,
            order="W1234",
            phase="42",
            length=200.0,
            width=150.0,
        )
        text = write_nc1(part)
        lines = text.split("\n")
        assert lines[0] == "ST"
        assert lines[1] == "** mypart.nc1"
        assert lines[2] == "  W1234"
        assert lines[3] == "  mypart"
        assert lines[4] == "  42"
        assert lines[5] == "  mypart"
        assert lines[6] == "  350W"
        assert lines[7] == "  5"
        assert lines[8] == "  PL25"
        assert lines[9] == "  B"
        # length/width
        assert float(lines[10].strip()) == 200.0
        assert float(lines[11].strip()) == 150.0

    def test_holes_in_output(self):
        part = Part(
            name="holed",
            outer=[
                Seg((0, 0), (200, 0)),
                Seg((200, 0), (200, 200)),
                Seg((200, 200), (0, 200)),
                Seg((0, 200), (0, 0)),
            ],
            holes=[(50.0, 50.0, 24.0), (150.0, 150.0, 20.0)],
            thickness=12.0,
            grade="S275",
            qty=1,
            length=200.0,
            width=200.0,
        )
        text = write_nc1(part)
        assert "BO\n" in text
        assert "24.00" in text
        assert "20.00" in text
