

import sys
from collections import deque

import numpy as np
import serial
import serial.tools.list_ports as list_ports

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


# ────────────────────────────── Config ──────────────────────────────
BAUD = 115200
POINTS = 150
POLL_MS = 20

APP_BG = "#eef1f5"
PANEL_BG = "#ffffff"
BORDER = "#d7dbe2"
GRID = "#e3e6ec"
TEXT = "#20242c"
SUBTEXT = "#6b7280"

PHASE_COLORS = {
    "A": "#1f4e79",   # navy
    "B": "#b5451f",   # rust
    "C": "#2f7d5a",   # forest green
    "REF": "#8a8f99", # gray, dashed
}
DQ_COLORS = {"D": "#6a4c93", "Q": "#c98a2b"}
FLUX_COLOR = "#a83246"


# ─────────────────────────── Serial link (RX + TX) ───────────────────────────
class SerialLink(QtCore.QThread):
    sample = QtCore.pyqtSignal(tuple)
    status = QtCore.pyqtSignal(str, bool)

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
                if len(parts) != 11:
                    continue
                ia, ib, ic, iref, idc, iq, flux, s1, s2, s3, rpm = (float(x) for x in parts)
                self.sample.emit((
                    ia / 1000.0, ib / 1000.0, ic / 1000.0, iref / 1000.0,
                    idc / 1000.0, iq / 1000.0, flux / 1000.0,
                    int(s1), int(s2), int(s3), rpm,
                ))
            except Exception:
                continue

        if self._ser and self._ser.is_open:
            self._ser.close()

    def send_line(self, text):
        """Send a command line to the MCU, e.g. 'S1500'. Safe no-op if not connected."""
        if self._ser and self._ser.is_open:
            try:
                self._ser.write((text + "\n").encode("ascii"))
            except Exception:
                pass

    def stop(self):
        self._running = False
        self.wait(500)


# ─────────────────────────── Small flat status dot ───────────────────────────
class Dot(QtWidgets.QWidget):
    def __init__(self, color_on, parent=None):
        super().__init__(parent)
        self._on = False
        self._color_on = QtGui.QColor(color_on)
        self._color_off = QtGui.QColor("#d7dbe2")
        self.setFixedSize(14, 14)

    def set_state(self, on: bool):
        if on != self._on:
            self._on = on
            self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = self._color_on if self._on else self._color_off
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtGui.QPen(QtGui.QColor(BORDER), 1))
        painter.drawEllipse(1, 1, 11, 11)


class SwitchRow(QtWidgets.QWidget):
    def __init__(self, names, colors, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self.dots = []
        for name, color in zip(names, colors):
            item = QtWidgets.QHBoxLayout()
            item.setSpacing(6)
            dot = Dot(color)
            lbl = QtWidgets.QLabel(name)
            lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; font-weight:600;")
            item.addWidget(dot)
            item.addWidget(lbl)
            layout.addLayout(item)
            self.dots.append(dot)
        layout.addStretch()

    def set_states(self, states):
        for dot, state in zip(self.dots, states):
            dot.set_state(bool(state))


# ─────────────────────────── Digital readout card ───────────────────────────
class Readout(QtWidgets.QFrame):
    def __init__(self, title, unit, color, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(2)

        title_lbl = QtWidgets.QLabel(title.upper())
        title_lbl.setAlignment(QtCore.Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; font-weight:700; letter-spacing:2px; border:none;")

        self.value_lbl = QtWidgets.QLabel("0")
        self.value_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.value_lbl.setStyleSheet(
            f"color:{color}; font-size:42px; font-weight:700; border:none; "
            f"font-family:'Segoe UI','Arial',sans-serif;"
        )

        unit_lbl = QtWidgets.QLabel(unit)
        unit_lbl.setAlignment(QtCore.Qt.AlignCenter)
        unit_lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; font-weight:600; border:none;")

        layout.addWidget(title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addWidget(unit_lbl)

    def set_value(self, value, fmt="{:,.0f}"):
        self.value_lbl.setText(fmt.format(value))


# ─────────────────────────── Inline value label (under plots) ───────────────────────────
class InlineValue(QtWidgets.QWidget):
    def __init__(self, name, color, dashed=False, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        marker = QtWidgets.QFrame()
        marker.setFixedSize(14, 3)
        style = "dashed" if dashed else "solid"
        marker.setStyleSheet(f"border-top: 2px {style} {color}; background: transparent;")

        self.name_lbl = QtWidgets.QLabel(name)
        self.name_lbl.setStyleSheet(f"color:{TEXT}; font-size:11px; font-weight:600; border:none;")

        self.value_lbl = QtWidgets.QLabel("0.00 A")
        self.value_lbl.setStyleSheet(
            f"color:{SUBTEXT}; font-size:11px; border:none; font-family:'Consolas','DejaVu Sans Mono',monospace;"
        )

        layout.addWidget(marker)
        layout.addWidget(self.name_lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, value, unit="A"):
        self.value_lbl.setText(f"{value:+.2f} {unit}")


def make_inline_row(specs):
    row = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(row)
    layout.setContentsMargins(2, 2, 2, 2)
    layout.setSpacing(16)
    items = {}
    for key, name, color, dashed in specs:
        w = InlineValue(name, color, dashed)
        layout.addWidget(w)
        items[key] = w
    layout.addStretch()
    return row, items


# ─────────────────────────────── Main window ───────────────────────────────
class AcademicDashboard(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Drive — Live Dashboard")
        self.resize(1300, 820)

        self.link = None
        self.t = deque(maxlen=POINTS)
        self.buffers = {k: deque([0.0] * POINTS, maxlen=POINTS)
                         for k in ("ia", "ib", "ic", "iref", "id", "iq", "flux")}
        self.sample_count = 0
        self._pending_rpm = None
        self._pending_flux = None

        self._build_ui()
        self._apply_theme()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(POLL_MS)

    # ------------------------------------------------------------ UI build
    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        root.addLayout(self._build_topbar())
        root.addWidget(self._build_control_panel())

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, stretch=1)

        # ---- left: plots ----
        plots_col = QtWidgets.QVBoxLayout()
        plots_col.setSpacing(14)
        body.addLayout(plots_col, stretch=3)

        self.phase_plot = self._make_plot("Phase Currents", "Current (A)")
        self.dq_plot    = self._make_plot("dq-Frame Currents", "Current (A)")
        self.flux_plot  = self._make_plot("Estimated Rotor Flux Magnitude", "Flux (Wb)")

# ---------------- Phase currents ----------------
# Autoscale only this plot
        self.phase_plot.enableAutoRange(axis='y', enable=True)

# ---------------- dq currents -------------------
# Fixed scale
        self.dq_plot.enableAutoRange(axis='y', enable=False)
        self.dq_plot.setYRange(-10.0, 10.0)      # change to (-10,10) if needed

# ---------------- Flux --------------------------
        self.flux_plot.enableAutoRange(axis='y', enable=True)




        

        phase_row, self.phase_vals = make_inline_row([
            ("ia", "Ia", PHASE_COLORS["A"], False),
            ("ib", "Ib", PHASE_COLORS["B"], False),
            ("ic", "Ic", PHASE_COLORS["C"], False),
            ("iref", "Iref", PHASE_COLORS["REF"], True),
        ])
        dq_row, self.dq_vals = make_inline_row([
            ("id", "Id", DQ_COLORS["D"], False),
            ("iq", "Iq", DQ_COLORS["Q"], False),
        ])
        flux_row, self.flux_vals = make_inline_row([
            ("flux", "\u03c8r", FLUX_COLOR, False),
        ])

        plots_col.addWidget(self._panel(self.phase_plot, phase_row), stretch=3)
        plots_col.addWidget(self._panel(self.dq_plot, dq_row), stretch=3)
        plots_col.addWidget(self._panel(self.flux_plot, flux_row), stretch=2)

        pen_w = 1.6
        self.curve_ia = self.phase_plot.plot(pen=pg.mkPen(PHASE_COLORS["A"], width=pen_w))
        self.curve_ib = self.phase_plot.plot(pen=pg.mkPen(PHASE_COLORS["B"], width=pen_w))
        self.curve_ic = self.phase_plot.plot(pen=pg.mkPen(PHASE_COLORS["C"], width=pen_w))
        self.curve_iref = self.phase_plot.plot(
            pen=pg.mkPen(PHASE_COLORS["REF"], width=pen_w, style=QtCore.Qt.DashLine)
        )
        self.curve_id = self.dq_plot.plot(pen=pg.mkPen(DQ_COLORS["D"], width=pen_w))
        self.curve_iq = self.dq_plot.plot(pen=pg.mkPen(DQ_COLORS["Q"], width=pen_w))
        self.curve_flux = self.flux_plot.plot(pen=pg.mkPen(FLUX_COLOR, width=pen_w))

        for curve in (self.curve_ia, self.curve_ib, self.curve_ic, self.curve_iref,
                      self.curve_id, self.curve_iq, self.curve_flux):
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)

        # ---- right: readouts ----
        side_col = QtWidgets.QVBoxLayout()
        side_col.setSpacing(14)
        body.addLayout(side_col, stretch=1)

        self.rpm_readout = Readout("Speed", "RPM", PHASE_COLORS["A"])
        self.flux_readout = Readout("Rotor Flux", "Wb", FLUX_COLOR)

        self.id_readout = Readout("Id", "A", DQ_COLORS["D"])
        self.iq_readout = Readout("Iq", "A", DQ_COLORS["Q"])

        side_col.addWidget(self.rpm_readout)
        side_col.addWidget(self.flux_readout)
        side_col.addWidget(self.id_readout)
        side_col.addWidget(self.iq_readout)

        switches_card = QtWidgets.QFrame()
        switches_card.setObjectName("card")
        sw_layout = QtWidgets.QVBoxLayout(switches_card)
        sw_layout.setContentsMargins(20, 14, 20, 14)
        sw_layout.setSpacing(8)
        sw_title = QtWidgets.QLabel("UPPER SWITCHES")
        sw_title.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; font-weight:700; letter-spacing:2px; border:none;")
        self.switch_row = SwitchRow(
            ["SW A", "SW B", "SW C"],
            [PHASE_COLORS["A"], PHASE_COLORS["B"], PHASE_COLORS["C"]],
        )
        sw_layout.addWidget(sw_title)
        sw_layout.addWidget(self.switch_row)
        side_col.addWidget(switches_card)

        side_col.addStretch()

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Disconnected")

    def _build_topbar(self):
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(10)

        title = QtWidgets.QLabel("Motor Drive — Live Dashboard")
        title.setStyleSheet(f"color:{TEXT}; font-size:19px; font-weight:700;")
        bar.addWidget(title)
        bar.addStretch()

        bar.addWidget(self._label("Port"))
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(130)
        self._refresh_ports()
        bar.addWidget(self.port_combo)

        refresh_btn = QtWidgets.QPushButton("\u27f3")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(self._refresh_ports)
        bar.addWidget(refresh_btn)

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.clicked.connect(self._toggle_connection)
        bar.addWidget(self.connect_btn)

        self.conn_dot = Dot("#2f7d5a")
        bar.addWidget(self.conn_dot)
        return bar

    def _build_control_panel(self):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(28)

        title = QtWidgets.QLabel("CONTROL")
        title.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; font-weight:700; letter-spacing:2px; border:none;")
        layout.addWidget(title)

        self.speed_spin = QtWidgets.QDoubleSpinBox()
        self.speed_spin.setRange(0, 6000)
        self.speed_spin.setDecimals(0)
        self.speed_spin.setSuffix(" RPM")
        self.speed_spin.setValue(1000)
        layout.addLayout(self._field("Speed ref.", self.speed_spin, self._apply_speed))

        self.kp_spin = QtWidgets.QDoubleSpinBox()
        self.kp_spin.setRange(0, 5)
        self.kp_spin.setDecimals(4)
        self.kp_spin.setSingleStep(0.001)
        self.kp_spin.setValue(0.01)
        layout.addLayout(self._field("Kp", self.kp_spin, self._apply_kp))

        self.ki_spin = QtWidgets.QDoubleSpinBox()
        self.ki_spin.setRange(0, 5)
        self.ki_spin.setDecimals(4)
        self.ki_spin.setSingleStep(0.001)
        self.ki_spin.setValue(0.01)
        layout.addLayout(self._field("Ki", self.ki_spin, self._apply_ki))

        layout.addStretch()
        return card

    def _field(self, label_text, spinbox, apply_slot):
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(4)
        lbl = QtWidgets.QLabel(label_text)
        lbl.setStyleSheet(f"color:{TEXT}; font-size:11px; font-weight:600; border:none;")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        spinbox.setFixedWidth(110)
        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setFixedWidth(60)
        apply_btn.clicked.connect(apply_slot)
        row.addWidget(spinbox)
        row.addWidget(apply_btn)
        col.addWidget(lbl)
        col.addLayout(row)
        return col

    def _label(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:12px;")
        return lbl

    def _make_plot(self, title, y_label):
        plot = pg.PlotWidget()
        plot.setBackground(PANEL_BG)
        plot.showGrid(x=True, y=True, alpha=0.35)
        plot.setLabel("left", y_label)
        plot.setLabel("bottom", "sample")
        plot.setTitle(title, color=TEXT, size="11pt")
        for axis in ("left", "bottom"):
            plot.getAxis(axis).setPen(pg.mkPen(GRID))
            plot.getAxis(axis).setTextPen(pg.mkPen(SUBTEXT))
        plot.setXRange(0, POINTS, padding=0.02)
        plot.enableAutoRange(axis="y", enable=True)
        plot.setMouseEnabled(x=True, y=True)
        plot.setMenuEnabled(False)
        return plot

    def _panel(self, plot_widget, footer):
        frame = QtWidgets.QFrame()
        frame.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(plot_widget, stretch=1)
        layout.addWidget(footer, stretch=0)
        return frame

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {APP_BG};
                color: {TEXT};
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 13px;
            }}
            #card {{
                background-color: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QPushButton {{
                background-color: #f2f4f7;
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 5px 12px;
                color: {TEXT};
            }}
            QPushButton:hover {{ background-color: #e6e9ee; }}
            #connectBtn {{
                background-color: #2f7d5a;
                color: white;
                font-weight: 700;
                border: none;
            }}
            #connectBtn:hover {{ background-color: #266a4b; }}
            QComboBox, QDoubleSpinBox {{
                background-color: #ffffff;
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QStatusBar {{ color: {SUBTEXT}; }}
        """)

    # ------------------------------------------------------- port / connect
    def _refresh_ports(self):
        self.port_combo.clear()
        ports = [p.device for p in list_ports.comports()]
        self.port_combo.addItems(ports if ports else ["No ports found"])

    def _toggle_connection(self):
        if self.link and self.link.isRunning():
            self.link.stop()
            self.link = None
            self.connect_btn.setText("Connect")
            self.conn_dot.set_state(False)
            self.status_bar.showMessage("Disconnected")
            return

        port = self.port_combo.currentText()
        if not port or "No ports" in port:
            self.status_bar.showMessage("No serial port selected")
            return

        self.link = SerialLink(port)
        self.link.sample.connect(self._on_sample)
        self.link.status.connect(self._on_status)
        self.link.start()
        self.connect_btn.setText("Disconnect")

    def _on_status(self, message, ok):
        self.status_bar.showMessage(message)
        self.conn_dot.set_state(ok)

    # ------------------------------------------------------- control -> MCU
    def _apply_speed(self):
        if self.link:
            self.link.send_line(f"S{self.speed_spin.value():.0f}")
            self.status_bar.showMessage(f"Speed reference set to {self.speed_spin.value():.0f} RPM", )

    def _apply_kp(self):
        if self.link:
            self.link.send_line(f"P{self.kp_spin.value():.4f}")
            self.status_bar.showMessage(f"Kp set to {self.kp_spin.value():.4f}")

    def _apply_ki(self):
        if self.link:
            self.link.send_line(f"I{self.ki_spin.value():.4f}")
            self.status_bar.showMessage(f"Ki set to {self.ki_spin.value():.4f}")

    # ------------------------------------------------------------ data flow
    def _on_sample(self, sample):
        ia, ib, ic, iref, idc, iq, flux, s1, s2, s3, rpm = sample
        self.sample_count += 1
        self.t.append(self.sample_count)
        self.buffers["ia"].append(ia)
        self.buffers["ib"].append(ib)
        self.buffers["ic"].append(ic)
        self.buffers["iref"].append(iref)
        self.buffers["id"].append(idc)
        self.buffers["iq"].append(iq)
        self.buffers["flux"].append(flux)
        self.switch_row.set_states([s1, s2, s3])
        self._pending_rpm = rpm
        self._pending_flux = flux

    def _refresh(self):
        if not self.t:
            return
        x = np.arange(len(self.t))
        self.curve_ia.setData(x, np.array(self.buffers["ia"]))
        self.curve_ib.setData(x, np.array(self.buffers["ib"]))
        self.curve_ic.setData(x, np.array(self.buffers["ic"]))
        self.curve_iref.setData(x, np.array(self.buffers["iref"]))
        self.curve_id.setData(x, np.array(self.buffers["id"]))
        self.curve_iq.setData(x, np.array(self.buffers["iq"]))
        self.curve_flux.setData(x, np.array(self.buffers["flux"]))

        if self._pending_rpm is not None:
            self.rpm_readout.set_value(self._pending_rpm)
            self._pending_rpm = None
        if self._pending_flux is not None:
            self.flux_readout.set_value(self._pending_flux, fmt="{:.3f}")
            self._pending_flux = None

        self.phase_vals["ia"].set_value(self.buffers["ia"][-1])
        self.phase_vals["ib"].set_value(self.buffers["ib"][-1])
        self.phase_vals["ic"].set_value(self.buffers["ic"][-1])
        self.phase_vals["iref"].set_value(self.buffers["iref"][-1])
        self.dq_vals["id"].set_value(self.buffers["id"][-1])
        self.dq_vals["iq"].set_value(self.buffers["iq"][-1])
        self.flux_vals["flux"].set_value(self.buffers["flux"][-1], unit="Wb")
        self.id_readout.set_value(self.buffers["id"][-1], fmt="{:+.2f}")
        self.iq_readout.set_value(self.buffers["iq"][-1], fmt="{:+.2f}")

    def closeEvent(self, event):
        if self.link:
            self.link.stop()
        event.accept()


def main():
    pg.setConfigOptions(antialias=True)
    app = QtWidgets.QApplication(sys.argv)
    win = AcademicDashboard()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()