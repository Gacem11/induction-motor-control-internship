import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import numpy as np

PORT   = 'COM4'
BAUD   = 115200
POINTS = 40

ser = serial.Serial(PORT, BAUD, timeout=0.01)

data1 = deque([0.0]*POINTS, maxlen=POINTS)   # Phase A measured
data2 = deque([0.0]*POINTS, maxlen=POINTS)   # Phase B measured
data3 = deque([0.0]*POINTS, maxlen=POINTS)   # Phase C measured
dataR = deque([0.0]*POINTS, maxlen=POINTS)   # Reference A
dataS1 = deque([0.0]*POINTS, maxlen=POINTS)  # Switch A
dataS2 = deque([0.0]*POINTS, maxlen=POINTS)  # Switch B
dataS3 = deque([0.0]*POINTS, maxlen=POINTS)  # Switch C

current_rpm = 0.0   # just the latest value, no history needed for a numeric readout

x = list(range(POINTS))

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                gridspec_kw={'height_ratios': [3, 1]})
fig.suptitle("Real Motor — Currents, Reference & Switch States", fontsize=14)

# ── Top plot: currents + reference ──
line1, = ax1.plot([], [], 'b', lw=1.5, label='Phase A')
line2, = ax1.plot([], [], 'r', lw=1.5, label='Phase B')
line3, = ax1.plot([], [], 'g', lw=1.5, label='Phase C')
lineR, = ax1.plot([], [], 'k--', lw=1.5, label='Reference A')

ax1.set_xlim(0, POINTS)
ax1.set_ylim(-6, 6)
ax1.set_ylabel("Current (A)")
ax1.axhline(0, color='gray', linewidth=0.5)
ax1.grid(True, alpha=0.3)
ax1.legend(loc='upper right', ncol=4, fontsize=9)

stats_text = ax1.text(0.01, 0.97, "", transform=ax1.transAxes,
                       fontsize=9, va='top', fontfamily='monospace',
                       bbox=dict(facecolor='white', alpha=0.85))

# ── RPM numeric readout (big number, top-right corner of the plot area) ──
rpm_text = ax1.text(0.99, 0.97, "", transform=ax1.transAxes,
                     fontsize=22, va='top', ha='right', fontweight='bold',
                     color='m',
                     bbox=dict(facecolor='white', alpha=0.85, edgecolor='m'))

# ── Bottom plot: switch states ──
lineS1, = ax2.plot([], [], 'b', lw=1.2, label='SW A (PB7)')
lineS2, = ax2.plot([], [], 'r', lw=1.2, label='SW B (PB8)')
lineS3, = ax2.plot([], [], 'g', lw=1.2, label='SW C (PB9)')

ax2.set_xlim(0, POINTS)
ax2.set_ylim(-0.3, 2.3)          # offset each switch vertically so they don't overlap
ax2.set_yticks([0, 1, 2])
ax2.set_yticklabels(['SW A', 'SW B', 'SW C'])
ax2.set_xlabel("Samples")
ax2.grid(True, alpha=0.3)


def update(frame):
    global current_rpm

    while ser.in_waiting:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            p = line.split(',')
            if len(p) == 8:
                m1 = float(p[0]) / 1000.0
                m2 = float(p[1]) / 1000.0
                m3 = float(p[2]) / 1000.0
                r1 = float(p[3]) / 1000.0
                s1 = float(p[4])
                s2 = float(p[5])
                s3 = float(p[6])
                current_rpm = float(p[7])   # just keep the latest value

                data1.append(m1)
                data2.append(m2)
                data3.append(m3)
                dataR.append(r1)

                # stack switches vertically: A at 0/1, B at 1/2, C at 2/3
                dataS1.append(s1)
                dataS2.append(s2 + 1.0)
                dataS3.append(s3 + 2.0)

        except Exception:
            pass

    y1 = np.array(data1)
    y2 = np.array(data2)
    y3 = np.array(data3)
    yR = np.array(dataR)

    line1.set_data(x, y1)
    line2.set_data(x, y2)
    line3.set_data(x, y3)
    lineR.set_data(x, yR)

    lineS1.set_data(x, list(dataS1))
    lineS2.set_data(x, list(dataS2))
    lineS3.set_data(x, list(dataS3))

    def rms(y):
        return np.sqrt(np.mean(y**2))

    stats_text.set_text(
        f"          RMS     MAX     MIN     P-P\n"
        f"Phase A  {rms(y1):6.2f}  {y1.max():6.2f}  {y1.min():6.2f}  {y1.max()-y1.min():6.2f}\n"
        f"Phase B  {rms(y2):6.2f}  {y2.max():6.2f}  {y2.min():6.2f}  {y2.max()-y2.min():6.2f}\n"
        f"Phase C  {rms(y3):6.2f}  {y3.max():6.2f}  {y3.min():6.2f}  {y3.max()-y3.min():6.2f}\n"
        f"Ref A    {rms(yR):6.2f}  {yR.max():6.2f}  {yR.min():6.2f}  {yR.max()-yR.min():6.2f}"
    )

    rpm_text.set_text(f"{current_rpm:.0f} RPM")

    return (
        line1,
        line2,
        line3,
        lineR,
        lineS1,
        lineS2,
        lineS3,
        stats_text,
        rpm_text,
    )

ani = animation.FuncAnimation(fig, update, interval=50,
                               blit=True, cache_frame_data=False)

plt.tight_layout()
plt.show()

ser.close()