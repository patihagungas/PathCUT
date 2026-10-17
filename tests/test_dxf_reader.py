"""DXF → NC1 regression suite.

Every reference DXF must produce NC1 output matching the reference NC1,
with the same painting surface tolerance as the roundtrip test.
"""

from pathlib import Path

import pytest

from plate_nesting.dxf.reader import read_dxf
from plate_nesting.nc1.writer import write_nc1

from .conftest import DXF_DIR, NC1_DIR

DXF_FILES = sorted(DXF_DIR.glob("*.dxf"))
PAINT_LINE = 18
PAINT_TOL = 0.003


@pytest.mark.parametrize(
    "dxf_file",
    DXF_FILES,
    ids=[f.stem for f in DXF_FILES],
)
def test_dxf_to_nc1(dxf_file: Path) -> None:
    """read_dxf(file) → Part → write_nc1(part) must match reference NC1."""
    nc1_file = NC1_DIR / f"{dxf_file.stem}.nc1"
    assert nc1_file.exists(), f"No reference NC1 for {dxf_file.stem}"

    ref = nc1_file.read_text().replace("\r\n", "\n")
    part = read_dxf(dxf_file)
    out = write_nc1(part)

    ref_lines = ref.split("\n")
    out_lines = out.split("\n")

    assert len(ref_lines) == len(out_lines), (
        f"Line count mismatch: ref={len(ref_lines)} out={len(out_lines)}"
    )

    for i, (r, o) in enumerate(zip(ref_lines, out_lines)):
        lineno = i + 1
        if lineno == PAINT_LINE:
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
