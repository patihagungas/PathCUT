"""PathCUT desktop application — convert-only mode."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

from plate_nesting.gui.converter import ConvertTab


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class PathCutApp(QMainWindow):
    """PathCUT desktop application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PathCUT")
        self.resize(1400, 900)
        self.setAcceptDrops(True)

        self._build_ui()

    # ---- UI construction ----

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self._convert_tab = ConvertTab()
        root.addWidget(self._convert_tab, stretch=1)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — drop or open DXF / NC1 files to convert")

    # ---- drag & drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".dxf", ".nc1")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        self._convert_tab.dropEvent(event)


# ---------------------------------------------------------------------------
# Dark Fusion theme
# ---------------------------------------------------------------------------

def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    dark = QColor(45, 45, 45)
    text = QColor(208, 208, 208)
    base = QColor(30, 30, 30)
    highlight = QColor(42, 130, 218)

    p.setColor(QPalette.ColorRole.Window, dark)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, dark)
    p.setColor(QPalette.ColorRole.ToolTipBase, dark)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, dark)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    p.setColor(QPalette.ColorRole.Link, highlight)
    p.setColor(QPalette.ColorRole.Highlight, highlight)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(p)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    # Set app icon — check PyInstaller bundle dir first, then source tree
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent.parent))
    ico = base / "pathcut.ico"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))
    window = PathCutApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
