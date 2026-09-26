"""
Motor Drive Live Dashboard
===========================
Real-time visualization of a hysteresis-controlled IRFOC motor drive:
  - Phase currents Ia, Ib, Ic + reference Ia
  - dq-frame currents Id, Iq
  - Upper-switch states (SW1/SW2/SW3) as LED indicators
  - Speed (RPM) as a large digital readout

Reads a 10-field CSV line over UART:
    i_a, i_b, i_c, i_ref_a, id, iq, sw1, sw2, sw3, rpm

Requirements (see requirements.txt):
    pip install PyQt5 pyqtgraph pyserial numpy

Usage:
    python motor_dashboard.py
"""

import sys
from collections import deque

import numpy as np
import serial
import serial.tools.list_ports as list_ports

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


# ────────────────────────────── Config ──────────────────────────────
BAUD = 115200
POINTS = 150           # samples kept on screen (smaller window = readable waveform)
POLL_MS = 20           # UI refresh period

COLOR_BG = "#12131a"
COLOR_PANEL = "#1b1d29"
COLOR_GRID = "#2a2d3d"
COLOR_TEXT = "#e6e6f0"
COLOR_ACCENT = "#7dd3fc"

PHASE_COLORS = {
    "A": "#3aa0ff",   # blue
    "B": "#ff5470",   # red
    "C": "#33e08a",   # green
    "REF": "#f5c451", # amber, dashed
}
DQ_COLORS = {"D": "#c084fc", "Q": "#fb923c"}


# ─────────────────────────── Serial reader thread ───────────────────────────
class SerialReader(QtCore.QThread):
    sample = QtCore.pyqtSignal(tuple)
    status = QtCore.pyqtSignal(str, bool)  # message, is_ok

    def __init__(self, port, baud=BAUD, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False
        self._ser = None

    def run(self):
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.05)
        except Exception as exc:
            self.status.emit(f"Could not open {self.port}: {exc}", False)
            return

        self._running = True
        self.status.emit(f"Connected to {self.port} @ {self.baud}", True)

        while self._running:
            try:
                raw = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                parts = raw.split(",")
                if len(parts) != 10:
                    continue
                ia, ib, ic, iref, idc, iq, s1, s2, s3, rpm = (float(x) for x in parts)
                self.sample.emit((
                    ia / 1000.0, ib / 1000.0, ic / 1000.0, iref / 1000.0,
                    idc / 1000.0, iq / 1000.0,
                    int(s1), int(s2), int(s3), rpm,
                ))
            except Exception:
                continue

        if self._ser and self._ser.is_open:
            self._ser.close()

    def stop(self):
        self._running = False
        self.wait(500)


# ─────────────────────────── LED indicator widget ───────────────────────────
class Led(QtWidgets.QWidget):
    def __init__(self, label, color_on, parent=None):
        super().__init__(parent)
        self._on = False
        self._color_on = QtGui.QColor(color_on)
        self._color_off = QtGui.QColor("#2a2d3d")
        self.setFixedSize(20, 20)
        self.label = label

    def set_state(self, on: bool):
        if on != self._on:
            self._on = on
            self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = self._color_on if self._on else self._color_off
        painter.setBrush(QtGui.QBrush(color))
        pen_color = color.lighter(140) if self._on else QtGui.QColor("#3a3d4d")
        painter.setPen(QtGui.QPen(pen_color, 1.5))
        painter.drawEllipse(1, 1, 17, 17)
        if self._on:
            glow = QtGui.QRadialGradient(10, 10, 12)
            glow.setColorAt(0, QtGui.QColor(color.red(), color.green(), color.blue(), 120))
            glow.setColorAt(1, QtGui.QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(QtGui.QBrush(glow))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(-4, -4, 28, 28)


class LedRow(QtWidgets.QWidget):
    def __init__(self, names, colors, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.leds = []
        for name, color in zip(names, colors):
            box = QtWidgets.QVBoxLayout()
            box.setSpacing(4)
            led = Led(name, color)
            lbl = QtWidgets.QLabel(name)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setStyleSheet(f"color:{COLOR_TEXT}; font-size:11px; font-weight:600;")
            led_wrap = QtWidgets.QHBoxLayout()
            led_wrap.addStretch()
            led_wrap.addWidget(led)
            led_wrap.addStretch()
            box.addLayout(led_wrap)
            box.addWidget(lbl)
            layout.addLayout(box)
            self.leds.append(led)

    def set_states(self, states):
        for led, state in zip(self.leds, states):
            led.set_state(bool(state))


# ─────────────────────────── Digital readout widget ───────────────────────────
class DigitalReadout(QtWidgets.QFrame):
    def __init__(self, title, unit, color=COLOR_ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("readout")
        self.setStyleSheet(f"""
            #readout {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_GRID};
                border-radius: 10px;
            }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)

        title_lbl = QtWidgets.QLabel(title.upper())
        title_lbl.setAlignment(QtCore.Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:#8b8fa3; font-size:12px; font-weight:700; letter-spacing:2px;"
        )

        self.value_lbl = QtWidgets.QLabel("0")
        self.value_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.value_lbl.setStyleSheet(
            f"color:{color}; font-size:52px; font-weight:800; font-family:'Consolas','DejaVu Sans Mono',monospace;"
        )

        unit_lbl = QtWidgets.QLabel(unit)
        unit_lbl.setAlignment(QtCore.Qt.AlignCenter)
        unit_lbl.setStyleSheet("color:#6b6f82; font-size:12px; font-weight:600;")

        layout.addWidget(title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addWidget(unit_lbl)

    def set_value(self, value, fmt="{:,.0f}"):
        self.value_lbl.setText(fmt.format(value))


class ValueChip(QtWidgets.QFrame):
    """Small dark pill showing a live instantaneous value, color-coded to
    match its curve — like an oscilloscope channel readout."""

    def __init__(self, name, unit, color, dashed=False, parent=None):
        super().__init__(parent)
        self.setObjectName("chip")
        border_style = "dashed" if dashed else "solid"
        self.setStyleSheet(f"""
            #chip {{
                background-color: #22253590;
                border: 1px solid {COLOR_GRID};
                border-left: 3px {border_style} {color};
                border-radius: 6px;
            }}
        """)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        name_lbl = QtWidgets.QLabel(name)
        name_lbl.setStyleSheet(f"color:{color}; font-size:12px; font-weight:700; border:none;")

        self.value_lbl = QtWidgets.QLabel("0.00")
        self.value_lbl.setStyleSheet(
            "color:#f2f2f7; font-size:16px; font-weight:700; border:none; "
            "font-family:'Consolas','DejaVu Sans Mono',monospace;"
        )
        unit_lbl = QtWidgets.QLabel(unit)
        unit_lbl.setStyleSheet("color:#6b6f82; font-size:11px; border:none;")

        layout.addWidget(name_lbl)
        layout.addStretch()
        layout.addWidget(self.value_lbl)
        layout.addWidget(unit_lbl)

    def set_value(self, value):
        self.value_lbl.setText(f"{value:+.2f}")


def make_value_row(specs):
    """specs: list of (key, name, unit, color, dashed) -> (row_widget, {key: ValueChip})"""
    row = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(row)
    layout.setContentsMargins(4, 0, 4, 4)
    layout.setSpacing(8)
    chips = {}
    for key, name, unit, color, dashed in specs:
        chip = ValueChip(name, unit, color, dashed)
        layout.addWidget(chip)
        chips[key] = chip
    return row, chips


# ─────────────────────────────── Main window ───────────────────────────────
class MotorDashboard(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Drive — Live Dashboard")
        self.resize(1280, 800)

        self.reader = None

        # ring buffers
        self.t = deque(maxlen=POINTS)
        self.buffers = {k: deque([0.0] * POINTS, maxlen=POINTS)
                         for k in ("ia", "ib", "ic", "iref", "id", "iq")}
        self.rpm_hist = deque([0.0] * POINTS, maxlen=POINTS)
        self.sample_count = 0

        self._build_ui()
        self._apply_theme()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._refresh_plots)
        self.timer.start(POLL_MS)

        self._pending = None  # latest sample waiting to be drawn

    # ---------------------------------------------------------- UI build
    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addLayout(self._build_toolbar())

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, stretch=1)

        # ---- left: plots ----
        plots_col = QtWidgets.QVBoxLayout()
        plots_col.setSpacing(14)
        body.addLayout(plots_col, stretch=3)

        self.phase_plot = self._make_plot("Phase Currents — Ia / Ib / Ic vs Reference", "A")
        self.dq_plot = self._make_plot("dq-Frame Currents — Id / Iq", "A")

        phase_value_row, self.phase_chips = make_value_row([
            ("ia", "Ia", "A", PHASE_COLORS["A"], False),
            ("ib", "Ib", "A", PHASE_COLORS["B"], False),
            ("ic", "Ic", "A", PHASE_COLORS["C"], False),
            ("iref", "Iref", "A", PHASE_COLORS["REF"], True),
        ])
        dq_value_row, self.dq_chips = make_value_row([
            ("id", "Id", "A", DQ_COLORS["D"], False),
            ("iq", "Iq", "A", DQ_COLORS["Q"], False),
        ])

        plots_col.addWidget(self._panel(self.phase_plot, footer=phase_value_row), stretch=3)
        plots_col.addWidget(self._panel(self.dq_plot, footer=dq_value_row), stretch=2)

        # thin, clean, antialiased traces — downsample/clip so dense
        # switching waveforms render as a crisp line instead of a blob
        pen_w = 1.6
        self.curve_ia = self.phase_plot.plot(pen=pg.mkPen(PHASE_COLORS["A"], width=pen_w), name="Ia")
        self.curve_ib = self.phase_plot.plot(pen=pg.mkPen(PHASE_COLORS["B"], width=pen_w), name="Ib")
        self.curve_ic = self.phase_plot.plot(pen=pg.mkPen(PHASE_COLORS["C"], width=pen_w), name="Ic")
        self.curve_iref = self.phase_plot.plot(
            pen=pg.mkPen(PHASE_COLORS["REF"], width=pen_w, style=QtCore.Qt.DashLine), name="Iref A"
        )
        self.phase_plot.addLegend(offset=(10, 6))

        self.curve_id = self.dq_plot.plot(pen=pg.mkPen(DQ_COLORS["D"], width=pen_w), name="Id")
        self.curve_iq = self.dq_plot.plot(pen=pg.mkPen(DQ_COLORS["Q"], width=pen_w), name="Iq")
        self.dq_plot.addLegend(offset=(10, 6))

        for curve in (self.curve_ia, self.curve_ib, self.curve_ic, self.curve_iref,
                      self.curve_id, self.curve_iq):
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)

        # ---- right: readouts ----
        side_col = QtWidgets.QVBoxLayout()
        side_col.setSpacing(14)
        body.addLayout(side_col, stretch=1)

        self.rpm_readout = DigitalReadout("Speed", "RPM", color="#7dd3fc")
        side_col.addWidget(self.rpm_readout)

        stats_panel = QtWidgets.QFrame()
        stats_panel.setObjectName("panel")
        stats_layout = QtWidgets.QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(16, 14, 16, 14)
        stats_layout.setSpacing(8)

        stats_title = QtWidgets.QLabel("UPPER SWITCHES")
        stats_title.setStyleSheet("color:#8b8fa3; font-size:12px; font-weight:700; letter-spacing:2px;")
        stats_layout.addWidget(stats_title)

        self.led_row = LedRow(
            ["SW A", "SW B", "SW C"],
            [PHASE_COLORS["A"], PHASE_COLORS["B"], PHASE_COLORS["C"]],
        )
        stats_layout.addWidget(self.led_row)
        side_col.addWidget(stats_panel)

        # live RMS / peak table
        table_panel = QtWidgets.QFrame()
        table_panel.setObjectName("panel")
        table_layout = QtWidgets.QVBoxLayout(table_panel)
        table_layout.setContentsMargins(16, 14, 16, 14)
        table_title = QtWidgets.QLabel("CURRENT STATISTICS")
        table_title.setStyleSheet("color:#8b8fa3; font-size:12px; font-weight:700; letter-spacing:2px;")
        table_layout.addWidget(table_title)

        self.stats_table = QtWidgets.QTableWidget(4, 3)
        self.stats_table.setHorizontalHeaderLabels(["RMS", "Max", "Min"])
        self.stats_table.setVerticalHeaderLabels(["Ia", "Ib", "Ic", "Iref"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.stats_table.verticalHeader().setDefaultSectionSize(26)
        self.stats_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.stats_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.stats_table.setFixedHeight(150)
        table_layout.addWidget(self.stats_table)
        side_col.addWidget(table_panel)

        side_col.addStretch()

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Disconnected")

    def _build_toolbar(self):
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(10)

        title = QtWidgets.QLabel("MOTOR DRIVE — LIVE DASHBOARD")
        title.setStyleSheet(f"color:{COLOR_TEXT}; font-size:18px; font-weight:800; letter-spacing:1px;")
        bar.addWidget(title)
        bar.addStretch()

        bar.addWidget(QtWidgets.QLabel("Port:"))
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(140)
        self._refresh_ports()
        bar.addWidget(self.port_combo)

        refresh_btn = QtWidgets.QPushButton("⟳")
        refresh_btn.setFixedWidth(32)
        refresh_btn.clicked.connect(self._refresh_ports)
        bar.addWidget(refresh_btn)

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.clicked.connect(self._toggle_connection)
        bar.addWidget(self.connect_btn)

        self.conn_led = Led("conn", "#33e08a")
        bar.addWidget(self.conn_led)

        return bar

    def _make_plot(self, title, y_label):
        plot = pg.PlotWidget()
        plot.setBackground(COLOR_PANEL)
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.setLabel("left", y_label)
        plot.setLabel("bottom", "sample")
        plot.setTitle(title, color=COLOR_TEXT, size="11pt")
        plot.getAxis("left").setPen(pg.mkPen(COLOR_GRID))
        plot.getAxis("bottom").setPen(pg.mkPen(COLOR_GRID))
        plot.getAxis("left").setTextPen(pg.mkPen(COLOR_TEXT))
        plot.getAxis("bottom").setTextPen(pg.mkPen(COLOR_TEXT))
        plot.setXRange(0, POINTS, padding=0.02)
        plot.enableAutoRange(axis="y", enable=True)
        plot.setAutoVisible(y=True)
        plot.setMouseEnabled(x=True, y=True)
        plot.setMenuEnabled(False)
        return plot

    def _panel(self, widget, footer=None):
        frame = QtWidgets.QFrame()
        frame.setObjectName("panel")
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(widget, stretch=1)
        if footer is not None:
            layout.addWidget(footer, stretch=0)
        return frame

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {COLOR_BG};
                color: {COLOR_TEXT};
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
            }}
            #panel {{
                background-color: {COLOR_PANEL};
                border: 1px solid {COLOR_GRID};
                border-radius: 10px;
            }}
            QPushButton {{
                background-color: #262a3d;
                border: 1px solid {COLOR_GRID};
                border-radius: 6px;
                padding: 6px 14px;
                color: {COLOR_TEXT};
            }}
            QPushButton:hover {{ background-color: #323752; }}
            #connectBtn {{
                background-color: #2c6e49;
                font-weight: 700;
            }}
            #connectBtn:hover {{ background-color: #35855a; }}
            QComboBox {{
                background-color: #262a3d;
                border: 1px solid {COLOR_GRID};
                border-radius: 6px;
                padding: 4px 10px;
            }}
            QTableWidget {{
                background-color: {COLOR_PANEL};
                gridline-color: {COLOR_GRID};
                border: none;
            }}
            QHeaderView::section {{
                background-color: #21243450;
                color: #8b8fa3;
                border: none;
                padding: 4px;
            }}
            QStatusBar {{ color: #8b8fa3; }}
        """)

    # ------------------------------------------------------- port / connect
    def _refresh_ports(self):
        self.port_combo.clear()
        ports = [p.device for p in list_ports.comports()]
        self.port_combo.addItems(ports if ports else ["No ports found"])

    def _toggle_connection(self):
        if self.reader and self.reader.isRunning():
            self.reader.stop()
            self.reader = None
            self.connect_btn.setText("Connect")
            self.conn_led.set_state(False)
            self.status_bar.showMessage("Disconnected")
            return

        port = self.port_combo.currentText()
        if not port or "No ports" in port:
            self.status_bar.showMessage("No serial port selected")
            return

        self.reader = SerialReader(port)
        self.reader.sample.connect(self._on_sample)
        self.reader.status.connect(self._on_status)
        self.reader.start()
        self.connect_btn.setText("Disconnect")

    def _on_status(self, message, ok):
        self.status_bar.showMessage(message)
        self.conn_led.set_state(ok)

    # ------------------------------------------------------------ data flow
    def _on_sample(self, sample):
        ia, ib, ic, iref, idc, iq, s1, s2, s3, rpm = sample
        self.sample_count += 1
        self.t.append(self.sample_count)
        self.buffers["ia"].append(ia)
        self.buffers["ib"].append(ib)
        self.buffers["ic"].append(ic)
        self.buffers["iref"].append(iref)
        self.buffers["id"].append(idc)
        self.buffers["iq"].append(iq)
        self.rpm_hist.append(rpm)
        self.led_row.set_states([s1, s2, s3])
        self._pending = rpm

    def _refresh_plots(self):
        if not self.t:
            return
        x = np.arange(len(self.t))
        self.curve_ia.setData(x, np.array(self.buffers["ia"]))
        self.curve_ib.setData(x, np.array(self.buffers["ib"]))
        self.curve_ic.setData(x, np.array(self.buffers["ic"]))
        self.curve_iref.setData(x, np.array(self.buffers["iref"]))
        self.curve_id.setData(x, np.array(self.buffers["id"]))
        self.curve_iq.setData(x, np.array(self.buffers["iq"]))

        if self._pending is not None:
            self.rpm_readout.set_value(self._pending)
            self._pending = None

        # live instantaneous values (last sample in each buffer)
        self.phase_chips["ia"].set_value(self.buffers["ia"][-1])
        self.phase_chips["ib"].set_value(self.buffers["ib"][-1])
        self.phase_chips["ic"].set_value(self.buffers["ic"][-1])
        self.phase_chips["iref"].set_value(self.buffers["iref"][-1])
        self.dq_chips["id"].set_value(self.buffers["id"][-1])
        self.dq_chips["iq"].set_value(self.buffers["iq"][-1])

        self._update_stats()

    def _update_stats(self):
        def rms(a):
            return float(np.sqrt(np.mean(a ** 2))) if len(a) else 0.0

        rows = [
            ("Ia", np.array(self.buffers["ia"])),
            ("Ib", np.array(self.buffers["ib"])),
            ("Ic", np.array(self.buffers["ic"])),
            ("Iref", np.array(self.buffers["iref"])),
        ]
        for row, (_, arr) in enumerate(rows):
            values = [rms(arr), arr.max() if len(arr) else 0.0, arr.min() if len(arr) else 0.0]
            for col, val in enumerate(values):
                item = QtWidgets.QTableWidgetItem(f"{val:.2f}")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.stats_table.setItem(row, col, item)

    def closeEvent(self, event):
        if self.reader:
            self.reader.stop()
        event.accept()


def main():
    pg.setConfigOptions(antialias=True)
    app = QtWidgets.QApplication(sys.argv)
    win = MotorDashboard()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()