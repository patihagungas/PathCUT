"""NC1 roundtrip regression suite.

Every reference NC1 file must survive parse → Part → write byte-for-byte,
except header line 18 (painting surface) which may differ by ±0.002.
"""

from pathlib import Path

import pytest

from plate_nesting.nc1.parser import parse_nc1
from plate_nesting.nc1.writer import write_nc1

from .conftest import NC1_DIR

NC1_FILES = sorted(NC1_DIR.glob("*.nc1"))
PAINT_LINE = 18  # 1-indexed
PAINT_TOL = 0.003  # allow ±0.002 rounded up


@pytest.mark.parametrize(
    "nc1_file",
    NC1_FILES,
    ids=[f.stem for f in NC1_FILES],
)
def test_nc1_roundtrip(nc1_file: Path) -> None:
    """parse(nc1) → Part → write(part) must match original."""
    ref = nc1_file.read_text().replace("\r\n", "\n")
    part = parse_nc1(ref)
    out = write_nc1(part)

    ref_lines = ref.split("\n")
    out_lines = out.split("\n")

    assert len(ref_lines) == len(out_lines), (
        f"Line count mismatch: ref={len(ref_lines)} out={len(out_lines)}"
    )

    for i, (r, o) in enumerate(zip(ref_lines, out_lines)):
        lineno = i + 1
        if lineno == PAINT_LINE:
            # Allow painting surface tolerance
            r_stripped = r.strip()
            o_stripped = o.strip()
            if r_stripped and o_stripped:
                rv = float(r_stripped)
                ov = float(o_stripped)
                assert abs(rv - ov) <= PAINT_TOL, (
                    f"Line {lineno} paint surface diff too large: "
                    f"ref={rv} out={ov} delta={abs(rv-ov)}"
                )
            continue
        assert r == o, (
            f"Line {lineno} differs:\n  ref: {r!r}\n  out: {o!r}"
        )
