import sys
from PySide6 import QtWidgets, QtCore, QtGui
import asyncio
try:
    from tastytrade.dxfeed import DXLinkStreamer, OptionSale
except ImportError:  # tastytrade not installed; placeholders for type checkers
    DXLinkStreamer = object
    OptionSale = object

SNAP_DISTANCE = 10

class PowerMeter(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Window)
        self.setMinimumSize(40, 150)
        self._setup_ui()
        self.snapped_to = []
        self.symbol = "SPX"
        self.worker = None

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

        self.reset_btn = QtWidgets.QPushButton("R")
        self.reset_btn.setFixedSize(20, 20)
        self.invert_btn = QtWidgets.QPushButton("\u2195")
        self.invert_btn.setFixedSize(20, 20)

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
        self.canvas = QtWidgets.QFrame()
        self.canvas.setStyleSheet("background-color:#202020")
        canvas_layout = QtWidgets.QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(2, 2, 2, 2)
        canvas_layout.setSpacing(0)
        self.buy_label = QtWidgets.QLabel("0")
        self.buy_label.setAlignment(QtCore.Qt.AlignCenter)
        self.buy_label.setStyleSheet("color:white")
        self.sell_label = QtWidgets.QLabel("0")
        self.sell_label.setAlignment(QtCore.Qt.AlignCenter)
        self.sell_label.setStyleSheet("color:white")
        canvas_layout.addWidget(self.buy_label)
        canvas_layout.addWidget(self.sell_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.canvas, 1)

    def start_stream(self, symbol):
        self.symbol = symbol
        if self.worker:
            self.worker.stop()
        self.worker = DataWorker(symbol)
        self.worker.data.connect(self.update_totals)
        self.worker.start()

    @QtCore.Slot(int, int)
    def update_totals(self, buys, sells):
        self.buy_label.setText(str(buys))
        self.sell_label.setText(str(sells))

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        return super().closeEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if SnapManager.enabled:
            SnapManager.check_snap(self)

class SnapManager:
    windows = []
    enabled = True

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
            dx = other.x() - (win.x() + win.width())
            if abs(dx) <= SNAP_DISTANCE:
                if abs(other.y() - win.y()) <= SNAP_DISTANCE:
                    win.move(other.x() - win.width(), other.y())
                    win.snapped_to.append(other)
                    break


class DataWorker(QtCore.QThread):
    """Background worker that streams prints from dxFeed."""

    data = QtCore.Signal(int, int)

    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol
        self.buy_total = 0
        self.sell_total = 0
        self._running = True

    async def _listen(self):
        """Internal async loop that reconnects on errors."""
        if DXLinkStreamer is object:
            return
        while self._running:
            try:
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
            except Exception:
                await asyncio.sleep(3)

    def run(self) -> None:
        asyncio.run(self._listen())

    def stop(self) -> None:
        self._running = False

class ControlPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Panel")
        self.layout = QtWidgets.QVBoxLayout(self)
        self.add_btn = QtWidgets.QPushButton("Add Meter")
        self.add_btn.clicked.connect(self.add_meter)
        self.layout.addWidget(self.add_btn)
        self.meters = []
        self.add_meter()

    def add_meter(self):
        meter = PowerMeter()
        SnapManager.add(meter)
        meter.show()
        meter.start_stream("SPX")
        self.meters.append(meter)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec())
