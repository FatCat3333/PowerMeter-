import sys
import json
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui
import asyncio
try:
    from tastytrade.dxfeed import DXLinkStreamer, OptionSale
except ImportError:  # tastytrade not installed; placeholders for type checkers
    DXLinkStreamer = object
    OptionSale = object

SNAP_DISTANCE = 10
CONFIG_DIR = Path(QtCore.QStandardPaths.writableLocation(
    QtCore.QStandardPaths.AppDataLocation))
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "always_on_top": True,
    "snap_enabled": True,
    "border_width": 1,
}


def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(data)
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


class Canvas(QtWidgets.QFrame):
    def __init__(self, meter):
        super().__init__()
        self.meter = meter
        self.setStyleSheet("background-color:#202020")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        w = self.width()
        h = self.height()
        centre = h / 2

        bw = self.meter.buy_total
        sw = self.meter.sell_total
        total = bw + sw
        if total == 0:
            ratio = 0
        else:
            ratio = bw / total
        top_height = centre * (ratio if not self.meter.inverted else 1 - ratio)
        bottom_height = h - top_height*2

        painter.setPen(QtCore.Qt.NoPen)
        # blue buy bar
        painter.setBrush(QtGui.QColor("#2196F3"))
        if self.meter.inverted:
            painter.drawRect(0, 0, w, centre - top_height)
        else:
            painter.drawRect(0, centre - top_height, w, top_height)
        # red sell bar
        painter.setBrush(QtGui.QColor("#B32025"))
        if self.meter.inverted:
            painter.drawRect(0, centre + top_height, w, centre - top_height)
        else:
            painter.drawRect(0, centre, w, centre - top_height)

        pen = QtGui.QPen(QtGui.QColor("#000"))
        pen.setWidth(self.meter.main_tick_width)
        painter.setPen(pen)
        painter.drawLine(0, centre, w, centre)

        pen.setWidth(self.meter.half_tick_width)
        pen.setColor(QtGui.QColor(0,0,0,200))
        painter.setPen(pen)
        painter.drawLine(0, centre/2, w*0.5, centre/2)
        painter.drawLine(0, centre*1.5, w*0.5, centre*1.5)

        pen.setWidth(self.meter.quarter_tick_width)
        pen.setColor(QtGui.QColor(0,0,0,165))
        painter.setPen(pen)
        painter.drawLine(0, centre/4, w*0.25, centre/4)
        painter.drawLine(0, centre*0.75, w*0.25, centre*0.75)
        painter.drawLine(0, centre*1.25, w*0.25, centre*1.25)
        painter.drawLine(0, centre*1.75, w*0.25, centre*1.75)

        painter.end()

class PowerMeter(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Window)
        self.setMinimumSize(40, 150)
        self._setup_ui()
        # track neighbours this window is snapped to and the side of attachment
        # e.g. {other_window: "left"}
        self.snapped_to = {}
        self.symbol = "SPX"
        self.worker = None
        self.buy_total = 0
        self.sell_total = 0
        self.inverted = False
        self.auto_reset = False
        self.flash_color = QtGui.QColor("#00BFFF")
        self.main_tick_width = 2
        self.half_tick_width = 1
        self.quarter_tick_width = 1

        self.flash_timer = QtCore.QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self._end_flash)

        self.reset_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.reset_btn.customContextMenuRequested.connect(self._reset_all)

    def _setup_ui(self):
        self.strike_edit = QtWidgets.QLineEdit("5900")
        self.strike_edit.setFixedHeight(22)
        self.calendar_btn = QtWidgets.QToolButton()
        self.calendar_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        self.calendar_btn.setFixedSize(14, 14)

        strike_layout = QtWidgets.QHBoxLayout()
        strike_layout.setContentsMargins(0, 0, 0, 0)
        strike_layout.addWidget(self.strike_edit)
        strike_layout.addWidget(self.calendar_btn)

        self.call_put_btn = QtWidgets.QPushButton("CALL")
        self.call_put_btn.setFixedHeight(25)
        self.call_put_btn.setStyleSheet("background:#168336;color:#FFFFFF")
        self.call_put_btn.clicked.connect(self.toggle_call_put)

        self.reset_btn = QtWidgets.QPushButton("R")
        self.reset_btn.setFixedSize(20, 20)
        self.reset_btn.clicked.connect(self.reset)
        self.reset_btn.setStyleSheet("background:#1E74D2;color:white")
        self.invert_btn = QtWidgets.QPushButton("\u2195")
        self.invert_btn.setFixedSize(20, 20)
        self.invert_btn.setStyleSheet("background:#808080;color:white")
        self.invert_btn.clicked.connect(self.toggle_invert)

        side_layout = QtWidgets.QVBoxLayout()
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(2)
        side_layout.addWidget(self.reset_btn)
        side_layout.addWidget(self.invert_btn)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(2)
        header_left = QtWidgets.QVBoxLayout()
        header_left.setContentsMargins(0, 0, 0, 0)
        header_left.setSpacing(0)
        header_left.addLayout(strike_layout)
        header_left.addWidget(self.call_put_btn)

        header_layout.addLayout(header_left)
        header_layout.addStretch()
        header_layout.addLayout(side_layout)
        self.header = QtWidgets.QFrame()
        self.header.setLayout(header_layout)
        self.header.setStyleSheet("background-color:#333; color:white")
        self.canvas = Canvas(self)
        canvas_layout = QtWidgets.QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(2, 2, 2, 2)
        canvas_layout.setSpacing(0)
        font = QtGui.QFont("Consolas", 10)
        self.buy_label = QtWidgets.QLabel("0")
        self.buy_label.setAlignment(QtCore.Qt.AlignCenter)
        self.buy_label.setStyleSheet("color:white")
        self.buy_label.setFont(font)
        self.sell_label = QtWidgets.QLabel("0")
        self.sell_label.setAlignment(QtCore.Qt.AlignCenter)
        self.sell_label.setStyleSheet("color:white")
        self.sell_label.setFont(font)
        canvas_layout.addWidget(self.buy_label)
        canvas_layout.addWidget(self.sell_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.canvas, 1)

    def toggle_call_put(self):
        if self.call_put_btn.text() == "CALL":
            self.call_put_btn.setText("PUT")
            self.call_put_btn.setStyleSheet("background:#B32025;color:white")
        else:
            self.call_put_btn.setText("CALL")
            self.call_put_btn.setStyleSheet("background:#168336;color:white")

    def toggle_invert(self):
        self.inverted = not self.inverted
        if self.inverted:
            self.invert_btn.setStyleSheet("background:#E3A300;color:white")
        else:
            self.invert_btn.setStyleSheet("background:#808080;color:white")
        self.canvas.update()

    def stack_number(self, value):
        return "\n".join(str(value))

    def reset(self):
        self.buy_total = 0
        self.sell_total = 0
        self.update_labels()
        self.canvas.update()

    def _reset_all(self, *args):
        for m in SnapManager.windows:
            m.reset()

    def update_labels(self):
        self.buy_label.setText(self.stack_number(self.buy_total))
        self.sell_label.setText(self.stack_number(self.sell_total))

    def flash(self):
        palette = self.header.palette()
        self._orig_header_color = palette.color(QtGui.QPalette.Window)
        self.header.setStyleSheet(
            f"background-color:{self.flash_color.name()};color:white")
        self.setStyleSheet(f"border:{self.main_tick_width}px solid {self.flash_color.name()};")
        self.flash_timer.start(150)

    def _end_flash(self):
        self.header.setStyleSheet("background-color:#333; color:white")
        self.setStyleSheet("")

    def start_stream(self, symbol):
        self.symbol = symbol
        if self.worker:
            self.worker.stop()
        self.worker = DataWorker(symbol)
        self.worker.data.connect(self.update_totals)
        self.worker.start()

    @QtCore.Slot(int, int)
    def update_totals(self, buys, sells):
        self.buy_total = buys
        self.sell_total = sells
        self.update_labels()
        self.canvas.update()
        if self.auto_reset and self.buy_total == self.sell_total and self.buy_total != 0:
            self.reset()
            self.flash()

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        if self in SnapManager.windows:
            SnapManager.windows.remove(self)
        return super().closeEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if SnapManager.enabled and not SnapManager.propagating:
            SnapManager.check_snap(self)
            SnapManager.propagate(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if SnapManager.enabled and not SnapManager.propagating:
            SnapManager.propagate(self)

class SnapManager:
    windows = []
    enabled = True
    propagating = False

    @classmethod
    def add(cls, win):
        cls.windows.append(win)

    @classmethod
    def toggle(cls):
        cls.enabled = not cls.enabled
        if not cls.enabled:
            for w in cls.windows:
                w.snapped_to.clear()
        else:
            for w in cls.windows:
                cls.check_snap(w)

    @classmethod
    def check_snap(cls, win):
        if not cls.enabled:
            return
        for other in cls.windows:
            if other is win:
                continue
            gx, gy, gw, gh = win.geometry().getRect()
            ox, oy, ow, oh = other.geometry().getRect()
            # snap right edge of win to left edge of other
            if abs((gx + gw) - ox) <= SNAP_DISTANCE and abs(gy - oy) <= SNAP_DISTANCE:
                win.move(ox - gw, oy)
                win.snapped_to[other] = "right"
                other.snapped_to[win] = "left"
                return
            # snap left edge of win to right edge of other
            if abs(gx - (ox + ow)) <= SNAP_DISTANCE and abs(gy - oy) <= SNAP_DISTANCE:
                win.move(ox + ow, oy)
                win.snapped_to[other] = "left"
                other.snapped_to[win] = "right"
                return
            # snap top edge of win to bottom edge of other
            if abs(gy - (oy + oh)) <= SNAP_DISTANCE and abs(gx - ox) <= SNAP_DISTANCE:
                win.move(ox, oy + oh)
                win.snapped_to[other] = "top"
                other.snapped_to[win] = "bottom"
                return
            # snap bottom edge of win to top edge of other
            if abs((gy + gh) - oy) <= SNAP_DISTANCE and abs(gx - ox) <= SNAP_DISTANCE:
                win.move(ox, oy - gh)
                win.snapped_to[other] = "bottom"
                other.snapped_to[win] = "top"
                return

    @classmethod
    def propagate(cls, source):
        if cls.propagating:
            return
        cls.propagating = True
        try:
            for other, rel in source.snapped_to.items():
                if rel == "right":
                    other.move(source.x() + source.width(), source.y())
                elif rel == "left":
                    other.move(source.x() - other.width(), source.y())
                elif rel == "top":
                    other.move(source.x(), source.y() + source.height())
                elif rel == "bottom":
                    other.move(source.x(), source.y() - other.height())
        finally:
            cls.propagating = False


class DataWorker(QtCore.QThread):
    data = QtCore.Signal(int, int)

    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
        self.buy_total = 0
        self.sell_total = 0
        self._running = True

    async def _run_async(self):
        if DXLinkStreamer is object:
            return
        streamer = DXLinkStreamer()
        await streamer.login()
        await streamer.add_option_sales(self.symbol)
        async for sale in streamer.listen():
            if not self._running:
                break
            side = getattr(sale, "event_type", "")
            size = getattr(sale, "size", 0)
            if side == "B" or getattr(sale, "is_buy", False):
                self.buy_total += int(size)
            else:
                self.sell_total += int(size)
            self.data.emit(self.buy_total, self.sell_total)

    def run(self):
        asyncio.run(self._run_async())

    def stop(self):
        self._running = False

class ControlPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Panel")
        self.cfg = load_config()
        self.layout = QtWidgets.QVBoxLayout(self)

        self.add_btn = QtWidgets.QPushButton("Add Meter")
        self.add_btn.clicked.connect(self.add_meter)
        self.layout.addWidget(self.add_btn)

        self.snap_btn = QtWidgets.QPushButton("Toggle Snap (Ctrl+U)")
        self.snap_btn.setCheckable(True)
        self.snap_btn.setChecked(self.cfg.get("snap_enabled", True))
        self.snap_btn.clicked.connect(self.toggle_snap)
        self.layout.addWidget(self.snap_btn)

        self.top_btn = QtWidgets.QPushButton("Always On Top (Ctrl+Shift+T)")
        self.top_btn.setCheckable(True)
        self.top_btn.setChecked(self.cfg.get("always_on_top", True))
        self.top_btn.clicked.connect(self.toggle_top)
        self.layout.addWidget(self.top_btn)

        self.meters = []
        self.add_meter()

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+U"), self, activated=self.toggle_snap)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+T"), self, activated=self.toggle_top)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self.reset_focused)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+R"), self, activated=self.reset_all)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, activated=self.set_template)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Alt+T"), self, activated=self.resize_all)

    def toggle_snap(self):
        SnapManager.toggle()
        self.snap_btn.setChecked(SnapManager.enabled)

    def toggle_top(self):
        for m in self.meters:
            flags = m.windowFlags()
            if self.top_btn.isChecked():
                m.setWindowFlags(flags | QtCore.Qt.WindowStaysOnTopHint)
            else:
                m.setWindowFlags(flags & ~QtCore.Qt.WindowStaysOnTopHint)
            m.show()
        self.cfg["always_on_top"] = self.top_btn.isChecked()

    def add_meter(self):
        meter = PowerMeter()
        SnapManager.add(meter)
        if self.top_btn.isChecked():
            meter.setWindowFlags(meter.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        meter.show()
        meter.start_stream("SPX")
        self.meters.append(meter)

    def closeEvent(self, event):
        self.cfg["snap_enabled"] = SnapManager.enabled
        self.cfg["always_on_top"] = self.top_btn.isChecked()
        save_config(self.cfg)
        return super().closeEvent(event)

    def reset_focused(self):
        if self.meters:
            self.meters[-1].reset()

    def reset_all(self):
        for m in self.meters:
            m.reset()

    def set_template(self):
        if self.meters:
            self._template_size = self.meters[-1].size()

    def resize_all(self):
        if hasattr(self, "_template_size"):
            for m in self.meters:
                m.resize(self._template_size)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec())
