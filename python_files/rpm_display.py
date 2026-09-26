"""
RPM Dashboard for STM32 Motor Controller
Reads:  "RPM: %.1f | f_out: %.1f Hz  | befor filter: %.1f rpm\r\n"
Requires: pip install pyserial
"""

import tkinter as tk
import tkinter.font as tkfont
import serial
import serial.tools.list_ports
import threading
import math
import time

# ── CONFIG ─────────────────────────────────────────────
BAUD_RATE  = 115200
MAX_RPM    = 1700.0
# ────────────────────────────────────────────────────────

class Dashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Motor Dashboard")
        self.root.configure(bg="#0d0d0f")
        self.root.geometry("820x560")
        self.root.resizable(False, False)

        self.rpm          = 0.0
        self.rpm_raw      = 0.0
        self.f_out        = 0.0
        self.connected    = False
        self.ser          = None
        self.running      = True

        self._build_ui()
        self._scan_ports()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI BUILD ──────────────────────────────────────

    def _build_ui(self):
        bg = "#0d0d0f"

        # Title
        tk.Label(self.root, text="MOTOR CONTROL DASHBOARD",
                 bg=bg, fg="#3af0c8",
                 font=("Courier New", 13, "bold"),
                 letterSpacing=4).place(x=0, y=14, width=820)

        # ── Gauge canvas ──
        self.canvas = tk.Canvas(self.root, width=380, height=340,
                                bg=bg, highlightthickness=0)
        self.canvas.place(x=40, y=50)
        self._draw_gauge_static()

        # ── Right panel ──
        panel_x = 460

        # Filtered RPM big number
        tk.Label(self.root, text="FILTERED RPM",
                 bg=bg, fg="#555", font=("Courier New", 10)).place(x=panel_x, y=70)
        self.lbl_rpm = tk.Label(self.root, text="0.0",
                                bg=bg, fg="#3af0c8",
                                font=("Courier New", 52, "bold"))
        self.lbl_rpm.place(x=panel_x, y=88)

        # Raw RPM
        tk.Label(self.root, text="RAW RPM",
                 bg=bg, fg="#555", font=("Courier New", 10)).place(x=panel_x, y=190)
        self.lbl_raw = tk.Label(self.root, text="0.0",
                                bg=bg, fg="#f0a03a",
                                font=("Courier New", 28, "bold"))
        self.lbl_raw.place(x=panel_x, y=208)

        # f_out
        tk.Label(self.root, text="OUTPUT FREQUENCY",
                 bg=bg, fg="#555", font=("Courier New", 10)).place(x=panel_x, y=275)
        self.lbl_fout = tk.Label(self.root, text="0.0 Hz",
                                 bg=bg, fg="#a78bfa",
                                 font=("Courier New", 22, "bold"))
        self.lbl_fout.place(x=panel_x, y=293)

        # ── Port selector ──
        tk.Label(self.root, text="COM PORT",
                 bg=bg, fg="#555", font=("Courier New", 9)).place(x=panel_x, y=360)

        self.port_var = tk.StringVar()
        self.port_menu = tk.OptionMenu(self.root, self.port_var, "")
        self.port_menu.configure(bg="#1a1a22", fg="#ccc",
                                 activebackground="#2a2a35",
                                 font=("Courier New", 10),
                                 width=14, bd=0, highlightthickness=0)
        self.port_menu["menu"].configure(bg="#1a1a22", fg="#ccc",
                                         font=("Courier New", 10))
        self.port_menu.place(x=panel_x, y=380)

        # Connect button
        self.btn = tk.Button(self.root, text="CONNECT",
                             command=self._toggle_connect,
                             bg="#1a1a22", fg="#3af0c8",
                             activebackground="#2a2a35",
                             font=("Courier New", 11, "bold"),
                             width=12, bd=0, cursor="hand2")
        self.btn.place(x=panel_x, y=430)

        # Status
        self.lbl_status = tk.Label(self.root, text="● DISCONNECTED",
                                   bg=bg, fg="#f04a3a",
                                   font=("Courier New", 9))
        self.lbl_status.place(x=panel_x, y=480)

        # Refresh ports button
        tk.Button(self.root, text="↻ REFRESH PORTS",
                  command=self._scan_ports,
                  bg=bg, fg="#555",
                  activebackground=bg,
                  font=("Courier New", 9),
                  bd=0, cursor="hand2").place(x=panel_x, y=510)

    # ── GAUGE ─────────────────────────────────────────

    def _draw_gauge_static(self):
        cx, cy, r = 190, 190, 150
        c = self.canvas

        # Outer ring
        c.create_oval(cx-r-8, cy-r-8, cx+r+8, cy+r+8,
                      outline="#1e1e28", width=12)

        # Tick marks and labels
        for val in range(0, int(MAX_RPM)+1, 100):
            angle = self._rpm_to_angle(val)
            rad   = math.radians(angle)
            big   = (val % 500 == 0)
            r_in  = r - (18 if big else 10)
            x1 = cx + r * math.cos(rad)
            y1 = cy + r * math.sin(rad)
            x2 = cx + r_in * math.cos(rad)
            y2 = cy + r_in * math.sin(rad)
            c.create_line(x1, y1, x2, y2,
                          fill="#3af0c8" if big else "#2a3a35",
                          width=2 if big else 1)
            if big:
                lx = cx + (r - 34) * math.cos(rad)
                ly = cy + (r - 34) * math.sin(rad)
                c.create_text(lx, ly, text=str(val),
                              fill="#3af0c8", font=("Courier New", 8))

        # Arc background (gray track)
        self._draw_arc(cx, cy, r-20, 210, 300, "#1a2a24", width=14)

        # Center labels (placeholders replaced in update)
        self.gauge_arc   = None
        self.gauge_needle = None
        self.gauge_label  = c.create_text(cx, cy+55, text="0",
                                          fill="#3af0c8",
                                          font=("Courier New", 36, "bold"))
        self.gauge_unit   = c.create_text(cx, cy+92, text="RPM",
                                          fill="#3af0c8",
                                          font=("Courier New", 11))

        # Draw initial empty arc and needle
        self._update_gauge(0)

    def _rpm_to_angle(self, rpm):
        # 210 degrees = start (bottom-left), sweeps 300 degrees clockwise
        pct = min(rpm / MAX_RPM, 1.0)
        return 210 + pct * 300

    def _draw_arc(self, cx, cy, r, start_angle, extent, color, width=14):
        """Draw an arc on self.canvas."""
        x0, y0 = cx - r, cy - r
        x1, y1 = cx + r, cy + r
        return self.canvas.create_arc(x0, y0, x1, y1,
                                      start=-start_angle,
                                      extent=-extent,
                                      style=tk.ARC,
                                      outline=color,
                                      width=width)

    def _update_gauge(self, rpm):
        cx, cy, r = 190, 190, 150
        c = self.canvas

        # Remove old dynamic elements
        if self.gauge_arc:
            c.delete(self.gauge_arc)
        if self.gauge_needle:
            c.delete(self.gauge_needle)

        # Colored arc proportional to RPM
        pct    = min(rpm / MAX_RPM, 1.0)
        extent = pct * 300
        arc_color = self._rpm_color(rpm)
        if extent > 0:
            self.gauge_arc = self._draw_arc(cx, cy, r-20, 210, extent,
                                            arc_color, width=14)
        else:
            self.gauge_arc = None

        # Needle
        angle = math.radians(self._rpm_to_angle(rpm))
        nx = cx + (r - 30) * math.cos(angle)
        ny = cy + (r - 30) * math.sin(angle)
        self.gauge_needle = c.create_line(cx, cy, nx, ny,
                                          fill=arc_color, width=3,
                                          capstyle=tk.ROUND)

        # Center text
        c.itemconfigure(self.gauge_label, text=f"{rpm:.0f}",
                        fill=arc_color)

    def _rpm_color(self, rpm):
        pct = rpm / MAX_RPM
        if pct < 0.5:
            return "#3af0c8"   # teal
        elif pct < 0.8:
            return "#f0a03a"   # amber
        else:
            return "#f04a3a"   # red

    # ── SERIAL ────────────────────────────────────────

    def _scan_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        menu  = self.port_menu["menu"]
        menu.delete(0, "end")
        if not ports:
            ports = ["No ports found"]
        for p in ports:
            menu.add_command(label=p,
                             command=lambda v=p: self.port_var.set(v))
        self.port_var.set(ports[0])

    def _toggle_connect(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var.get()
        if not port or port == "No ports found":
            return
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
            self.connected = True
            self.btn.configure(text="DISCONNECT", fg="#f04a3a")
            self.lbl_status.configure(text=f"● CONNECTED  {port}",
                                      fg="#3af0c8")
            # Start reading thread
            t = threading.Thread(target=self._read_loop, daemon=True)
            t.start()
        except Exception as e:
            self.lbl_status.configure(text=f"ERROR: {e}", fg="#f04a3a")

    def _disconnect(self):
        self.connected = False
        if self.ser:
            self.ser.close()
        self.btn.configure(text="CONNECT", fg="#3af0c8")
        self.lbl_status.configure(text="● DISCONNECTED", fg="#f04a3a")

    def _read_loop(self):
        """Runs in background thread — reads serial lines."""
        while self.running and self.connected:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    self._parse_line(line)
            except:
                self._disconnect()
                break

    def _parse_line(self, line):
        """
        Expected format:
        RPM: 163.5 | f_out: 50.0 Hz  | befor filter: 170.2 rpm
        """
        try:
            rpm_part   = line.split("RPM:")[1].split("|")[0].strip()
            fout_part  = line.split("f_out:")[1].split("Hz")[0].strip()
            raw_part   = line.split("befor filter:")[1].split("rpm")[0].strip()

            self.rpm     = float(rpm_part)
            self.f_out   = float(fout_part)
            self.rpm_raw = float(raw_part)

            # Schedule UI update on main thread
            self.root.after(0, self._update_ui)
        except:
            pass   # ignore malformed lines silently

    def _update_ui(self):
        self._update_gauge(self.rpm)
        self.lbl_rpm.configure(text=f"{self.rpm:.1f}",
                               fg=self._rpm_color(self.rpm))
        self.lbl_raw.configure(text=f"{self.rpm_raw:.1f}")
        self.lbl_fout.configure(text=f"{self.f_out:.1f} Hz")

    def _on_close(self):
        self.running = False
        self._disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app  = Dashboard(root)
    root.mainloop()