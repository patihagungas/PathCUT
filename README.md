# Plate Nesting

Steel plate nesting application for structural steel fabrication. Converts DXF drawings to DSTV NC1 files and nests parts onto sheets for plasma/oxy-fuel cutting.

## Install (Windows)

```bash
pip install -e ".[dev]"
```

## Quickstart

```bash
# Convert a DXF to NC1
plate-nesting convert part.dxf

# Batch convert a folder
plate-nesting convert folder/*.dxf -o output/

# Import NC1 files and re-export
plate-nesting convert part.nc1
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/
mypy src/
```

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for module layout and design.
See [DECISIONS.md](DECISIONS.md) for technical decisions and rationale.
See [THIRD_PARTY.md](THIRD_PARTY.md) for dependency licenses.
