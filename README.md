# PathCUT

Desktop application for converting between DXF and DSTV NC1 file formats, built for structural steel plate fabrication.

## Features

- **DXF to NC1** -- read 2D CAD drawings and produce CNC-ready NC1 files
- **NC1 to DXF** -- convert NC1 files back to DXF for viewing in any CAD software
- **Batch conversion** -- load multiple files and convert them all at once
- **Drag & drop** -- drop DXF or NC1 files directly onto the window
- **Editable part table** -- review and modify name, dimensions, grade, thickness, and quantity before converting
- **Dark-themed GUI** -- PySide6 Fusion dark theme

## Install (End User)

Download and run `PathCUT-Setup.exe`. The installer places PathCUT in Program Files, creates Start Menu and optional Desktop shortcuts, and includes an uninstaller. No Python required.

See the [PathCUT User Guide (PDF)](PathCUT_User_Guide.pdf) for detailed usage instructions.

## Build the Installer

Prerequisites: Python 3.11+, PyInstaller, and [Inno Setup 6](https://jrsoftware.org/isdl.php).

```bash
pip install -e ".[gui]"
pip install pyinstaller
build_installer.bat
```

This produces:
- `dist\PathCUT\PathCUT.exe` -- standalone application folder
- `Output\PathCUT-Setup.exe` -- Windows installer

## Install (Developer)

```bash
pip install -e ".[dev,gui]"
```

### Run from source

```bash
python -m plate_nesting.gui.app
```

### Tests & linting

```bash
pytest
ruff check src/
mypy src/
```

## Project Structure

```
src/plate_nesting/
  gui/           PySide6 desktop application
    app.py       Main window, dark theme, entry point
    converter.py Convert tab UI (file table, settings ribbon, conversion logic)
  dxf/           DXF file I/O (via ezdxf)
    reader.py    DXF -> Part
    writer.py    Part -> DXF
  nc1/           DSTV NC1 file I/O
    parser.py    NC1 text -> Part
    writer.py    Part -> NC1 text
    _format.py   Shared constants and formatting helpers
  geometry/      Seg class, contour operations, area/perimeter
  models/        Part dataclass (central model used by all modules)
  cli/           CLI entry point
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full module layout and data flow.
See [DECISIONS.md](DECISIONS.md) for technical decisions and rationale.
See [THIRD_PARTY.md](THIRD_PARTY.md) for dependency licenses.

## License

MIT
