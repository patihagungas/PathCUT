"""Sheet rendering canvas — QGraphicsScene/View with Y-flip, zoom, pan."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainterPath,
    QPen,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from plate_nesting.cutting.common_cut import CommonCut
    from plate_nesting.geometry.seg import Seg
    from plate_nesting.models.layout import Layout, PlacedPart

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
CLR_SHEET_BG = QColor(30, 30, 30)
CLR_SHEET_BORDER = QColor(100, 100, 100)
CLR_PART = QColor(0, 180, 180)
CLR_PART_FILL = QColor(0, 180, 180, 60)
CLR_PART_SEL = QColor(255, 220, 50)
CLR_PART_SEL_FILL = QColor(255, 220, 50, 80)
CLR_PART_HOVER = QColor(0, 220, 220)
CLR_COMMON_CUT = QColor(255, 140, 0)
CLR_LABEL = QColor(200, 200, 200)

_LABEL_FONT = QFont("Arial")
_LABEL_FONT.setPixelSize(12)


# ---------------------------------------------------------------------------
# Seg → QPainterPath helpers
# ---------------------------------------------------------------------------

def _arc_mid_points(seg: Seg, tol: float = 0.3) -> list[tuple[float, float]]:
    """Intermediate polyline points for an arc (excluding start/end)."""
    assert seg.center is not None
    sweep_abs = abs(seg.sweep())
    r = seg.r
    if r < 1e-9 or r * (1 - math.cos(sweep_abs / 2)) <= tol:
        return []
    step = 2 * math.acos(max(-1.0, min(1.0, 1 - tol / r)))
    n = max(2, math.ceil(sweep_abs / step))
    cx, cy = seg.center
    a0 = math.atan2(seg.p0[1] - cy, seg.p0[0] - cx)
    signed = seg.sweep()
    return [
        (cx + r * math.cos(a0 + signed * i / n),
         cy + r * math.sin(a0 + signed * i / n))
        for i in range(1, n)
    ]


def segs_to_path(segs: list[Seg], tol: float = 0.3) -> QPainterPath:
    """Convert a closed segment loop to a *QPainterPath*."""
    path = QPainterPath()
    if not segs:
        return path
    path.moveTo(*segs[0].p0)
    for seg in segs:
        if seg.is_arc:
            for pt in _arc_mid_points(seg, tol):
                path.lineTo(*pt)
        path.lineTo(*seg.p1)
    path.closeSubpath()
    return path


# ---------------------------------------------------------------------------
# PlacedPart → world-coord helpers
# ---------------------------------------------------------------------------

def _transform_segs(segs: list[Seg], pp: PlacedPart) -> list[Seg]:
    """Apply mirror → rotate → translate (same pipeline as world_outer_edges)."""
    out = list(segs)
    if pp.mirrored:
        out = [s.mirrored_x() for s in out]
    if pp.rotation != 0.0:
        out = [s.rotated(pp.rotation) for s in out]
    return [s.shifted(pp.x, pp.y) for s in out]


def _transform_point(
    x: float, y: float, pp: PlacedPart
) -> tuple[float, float]:
    """Transform a single point through mirror → rotate → translate."""
    if pp.mirrored:
        x = -x
    if pp.rotation != 0.0:
        rad = math.radians(pp.rotation)
        c, s = math.cos(rad), math.sin(rad)
        x, y = x * c - y * s, x * s + y * c
    return x + pp.x, y + pp.y


def build_part_path(pp: PlacedPart) -> QPainterPath:
    """Full QPainterPath for a placed part (outer + inners + holes)."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)

    # Outer contour (uses PlacedPart's own method)
    outer = pp.world_outer_edges()
    if outer:
        path.addPath(segs_to_path(outer))

    # Inner cutouts — replicate the same Seg transform pipeline
    for inner in pp.part.inners:
        path.addPath(segs_to_path(_transform_segs(inner, pp)))

    # Circular holes
    for hx, hy, dia in pp.part.holes:
        wx, wy = _transform_point(hx, hy, pp)
        r = dia / 2
        path.addEllipse(wx - r, wy - r, dia, dia)

    return path


# ---------------------------------------------------------------------------
# Graphics items
# ---------------------------------------------------------------------------

class PartItem(QGraphicsPathItem):
    """Selectable / hoverable placed-part item."""

    def __init__(self, pp: PlacedPart, index: int, parent: QGraphicsItem | None = None):
        super().__init__(build_part_path(pp), parent)
        self.placement_index = index
        self.pp = pp

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self._pen_n = QPen(CLR_PART, 0.5)
        self._pen_s = QPen(CLR_PART_SEL, 1.0)
        self._pen_h = QPen(CLR_PART_HOVER, 0.8)
        self._brush_n = QBrush(CLR_PART_FILL)
        self._brush_s = QBrush(CLR_PART_SEL_FILL)

        self.setPen(self._pen_n)
        self.setBrush(self._brush_n)

    # ---- selection / hover feedback ----

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.setPen(self._pen_s)
                self.setBrush(self._brush_s)
                self.setZValue(10)
            else:
                self.setPen(self._pen_n)
                self.setBrush(self._brush_n)
                self.setZValue(0)
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):  # type: ignore[override]
        if not self.isSelected():
            self.setPen(self._pen_h)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # type: ignore[override]
        if not self.isSelected():
            self.setPen(self._pen_n)
        super().hoverLeaveEvent(event)


class CommonCutItem(QGraphicsLineItem):
    """Orange dashed line for a shared cut."""

    def __init__(self, cc: CommonCut, parent: QGraphicsItem | None = None):
        super().__init__(
            cc.cut_start[0], cc.cut_start[1],
            cc.cut_end[0], cc.cut_end[1],
            parent,
        )
        self.setPen(QPen(CLR_COMMON_CUT, 1.0, Qt.PenStyle.DashLine))
        self.setZValue(5)


# ---------------------------------------------------------------------------
# Scene / View
# ---------------------------------------------------------------------------

class SheetScene(QGraphicsScene):
    """Scene for one nested sheet layout."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor(20, 20, 20)))


class SheetView(QGraphicsView):
    """Interactive view with Y-flip, wheel zoom, middle-button pan."""

    part_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        from PySide6.QtGui import QPainter

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self._panning = False
        self._pan_start = None

    # ---- fit / zoom ----

    def fit_sheet(self) -> None:
        """Reset view to show the entire sheet with Y-up orientation."""
        sc = self.scene()
        if sc is None:
            return
        rect = sc.sceneRect()
        if rect.isEmpty():
            return
        self.resetTransform()
        self.fitInView(
            rect.adjusted(-20, -20, 20, 20),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        # Y-flip so scene Y-up maps to screen Y-down
        self.scale(1, -1)

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    # ---- middle-button pan ----

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._panning and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - delta.x())
            vs.setValue(vs.value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            # Emit click for left-button selection
            if event.button() == Qt.MouseButton.LeftButton:
                sel = self.scene().selectedItems() if self.scene() else []
                for item in sel:
                    if isinstance(item, PartItem):
                        self.part_clicked.emit(item.placement_index)
                        break


# ---------------------------------------------------------------------------
# populate_scene — draw everything for one Layout
# ---------------------------------------------------------------------------

def populate_scene(scene: SheetScene, layout: Layout) -> list[PartItem]:
    """Add sheet outline, parts with labels, and common cuts to *scene*."""
    scene.clear()
    sheet = layout.sheet

    # Sheet background rectangle
    bg = scene.addRect(
        0, 0, sheet.length, sheet.width,
        QPen(CLR_SHEET_BORDER, 1.0),
        QBrush(CLR_SHEET_BG),
    )
    bg.setZValue(-10)

    margin = 20.0
    scene.setSceneRect(
        -margin, -margin,
        sheet.length + 2 * margin,
        sheet.width + 2 * margin,
    )

    # Placed parts
    part_items: list[PartItem] = []
    for i, pp in enumerate(layout.placements):
        item = PartItem(pp, i)
        scene.addItem(item)
        part_items.append(item)

        # Text label — counter-flip so it reads right-side-up after view Y-flip
        label = QGraphicsSimpleTextItem(pp.part.name)
        label.setFont(_LABEL_FONT)
        label.setBrush(QBrush(CLR_LABEL))
        label.setTransform(QTransform(1, 0, 0, -1, 0, 0))
        label.setZValue(15)

        br = item.boundingRect()
        lbr = label.boundingRect()
        label.setPos(
            br.center().x() - lbr.width() / 2,
            br.center().y() + lbr.height() / 2,
        )
        scene.addItem(label)

    # Common cuts
    for cc in layout.common_cuts:
        scene.addItem(CommonCutItem(cc))

    return part_items
