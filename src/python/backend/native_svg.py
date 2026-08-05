from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtGui import QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Property, QRectF, QUrl, Signal
import os

class NativeSvgItem(QQuickPaintedItem):
    validChanged = Signal()
    animatedChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._renderer = QSvgRenderer()
        self._color = QColor("white")
        self._tint_enabled = True
        self._svg_path = ""
        self._valid = False
        self._animated = False
        
        # High-quality rendering settings
        self.setAntialiasing(True)
        self.setMipmap(True) 
        self.setRenderTarget(QQuickPaintedItem.RenderTarget.Image)
        self.setOpaquePainting(False)

        try:
            self._renderer.setAnimationEnabled(True)
        except Exception:
            pass

        try:
            self._renderer.repaintNeeded.connect(self._on_repaint_needed)
        except Exception:
            pass

    def _on_repaint_needed(self):
        self.update()

    def _set_status(self, valid: bool, animated: bool) -> None:
        valid_bool = bool(valid)
        animated_bool = bool(animated)
        if self._valid != valid_bool:
            self._valid = valid_bool
            self.validChanged.emit()
        if self._animated != animated_bool:
            self._animated = animated_bool
            self.animatedChanged.emit()

    def paint(self, painter):
        if not self._renderer.isValid():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        w = float(self.width())
        h = float(self.height())
        
        default_size = self._renderer.defaultSize()
        source_w = float(default_size.width()) if default_size.width() > 0 else w
        source_h = float(default_size.height()) if default_size.height() > 0 else h
        if source_w <= 0 or source_h <= 0:
            bounds = QRectF(0, 0, w, h)
        else:
            scale = min(w / source_w, h / source_h)
            draw_w = max(1.0, source_w * scale)
            draw_h = max(1.0, source_h * scale)
            draw_x = (w - draw_w) / 2.0
            draw_y = (h - draw_h) / 2.0
            bounds = QRectF(draw_x, draw_y, draw_w, draw_h)
        
        self._renderer.render(painter, bounds)

        if self._tint_enabled:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(bounds, self._color)

    # --- PROPERTIES ---
    def get_source(self): return self._svg_path
    def set_source(self, path):
        if self._svg_path != path:
            self._svg_path = path
            load_candidates = []

            try:
                maybe_url = QUrl(path)
                if maybe_url.isValid() and maybe_url.isLocalFile():
                    load_candidates.append(maybe_url.toLocalFile())
            except Exception:
                pass

            clean_path = path
            if path.startswith("file:///"):
                if os.name == "nt":
                    clean_path = path[8:]  # Windows: file:///C:/ -> C:/
                else:
                    clean_path = path[7:]  # Unix: file:///home -> /home
            load_candidates.append(clean_path)
            load_candidates.append(path)

            loaded = False
            for candidate in load_candidates:
                if not candidate:
                    continue
                if not os.path.exists(candidate):
                    continue
                try:
                    loaded = bool(self._renderer.load(candidate))
                except Exception:
                    loaded = False
                if loaded:
                    break

            if loaded and self._renderer.isValid():
                try:
                    self._renderer.setAnimationEnabled(True)
                except Exception:
                    pass
                self._set_status(True, bool(self._renderer.animated()))
                self.update()
            else:
                self._set_status(False, False)

    source = Property(str, get_source, set_source)

    def get_color(self): return self._color
    def set_color(self, color):
        if self._color != color:
            self._color = QColor(color)
            self.update()

    svgColor = Property(QColor, get_color, set_color)

    def get_tint_enabled(self): return self._tint_enabled
    def set_tint_enabled(self, enabled):
        enabled_bool = bool(enabled)
        if self._tint_enabled != enabled_bool:
            self._tint_enabled = enabled_bool
            self.update()

    tintEnabled = Property(bool, get_tint_enabled, set_tint_enabled)

    def get_valid(self):
        return self._valid

    valid = Property(bool, get_valid, notify=validChanged)

    def get_animated(self):
        return self._animated

    animated = Property(bool, get_animated, notify=animatedChanged)
