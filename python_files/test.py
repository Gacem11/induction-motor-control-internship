import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import numpy as np

PORT   = 'COM4'
BAUD   = 115200
POINTS = 200   # more points needed to see full sine cycles at 33.8Hz / 2kHz sample rate

ser = serial.Serial(PORT, BAUD, timeout=0.01)

dataA = deque([0.0]*POINTS, maxlen=POINTS)
dataB = deque([0.0]*POINTS, maxlen=POINTS)
dataC = deque([0.0]*POINTS, maxlen=POINTS)

x = list(range(POINTS))

fig, ax = plt.subplots(figsize=(12, 6))
fig.suptitle("IRFOC Test — dq_to_abc Reference Currents (simulated 1000rpm)", fontsize=13)

lineA, = ax.plot([], [], 'b', lw=1.5, label='ia_ref')
lineB, = ax.plot([], [], 'r', lw=1.5, label='ib_ref')
lineC, = ax.plot([], [], 'g', lw=1.5, label='ic_ref')

ax.set_xlim(0, POINTS)
ax.set_ylim(-1.5, 1.5)
ax.set_ylabel("Current (A)")
ax.set_xlabel("Samples")
ax.axhline(0, color='gray', linewidth=0.5)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')

def update(frame):
    while ser.in_waiting:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            p = line.split(',')
            if len(p) == 3:
                a = float(p[0]) / 1000.0
                b = float(p[1]) / 1000.0
                c = float(p[2]) / 1000.0
                dataA.append(a)
                dataB.append(b)
                dataC.append(c)
        except Exception:
            pass

    lineA.set_data(x, list(dataA))
    lineB.set_data(x, list(dataB))
    lineC.set_data(x, list(dataC))

    return (lineA, lineB, lineC)

ani = animation.FuncAnimation(fig, update, interval=50,
                               blit=True, cache_frame_data=False)

plt.tight_layout()
plt.show()

ser.close()