import sys
from PySide6 import QtWidgets, QtCore, QtGui

SNAP_DISTANCE = 10

class PowerMeter(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Window)
        self.setMinimumSize(40, 150)
        self._setup_ui()
        self.snapped_to = []

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

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.canvas, 1)

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
        self.meters.append(meter)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec())
