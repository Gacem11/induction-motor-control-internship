"""
Hysteresis Current Control — Real Motor Visualization
3 plots:
  1. Measured phase currents A, B, C  vs  3-phase reference
  2. Current error per phase (ref - measured)
  3. Switch states SW1 SW2 SW3
"""

import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import numpy as np

# ─────────────────────────────────────────
PORT    = 'COM4'
BAUD    = 115200
POINTS  = 300        # samples on screen
YLIM_I  = 6.0        # amps axis limit — increase if motor draws more
HYST_B  = 0.3        # must match HYST_BAND in control.h
# ─────────────────────────────────────────

try:
    ser = serial.Serial(PORT, BAUD, timeout=0.01)
    print(f"[OK] Serial open on {PORT}")
except Exception as e:
    print(f"[ERROR] {e}")
    ser = None

# Buffers
buf = {k: deque([0.0]*POINTS, maxlen=POINTS)
       for k in ['m1','m2','m3','r1','r2','r3',
                 'e1','e2','e3','s1','s2','s3']}
x = list(range(POINTS))

# ── Figure ───────────────────────────────
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 9))
fig.patch.set_facecolor('#1a1a2e')
fig.suptitle('Hysteresis Current Control — Motor Running',
             fontsize=13, color='white', fontweight='bold')

def style(ax, title, ylabel):
    ax.set_facecolor('#0d0d1a')
    ax.set_title(title, color='white', fontsize=10)
    ax.set_ylabel(ylabel, color='white', fontsize=9)
    ax.set_xlim(0, POINTS)
    ax.tick_params(colors='white', labelsize=8)
    ax.grid(True, color='#333355', lw=0.5)
    ax.axhline(0, color='white', lw=0.4, alpha=0.4)
    for sp in ax.spines.values():
        sp.set_edgecolor('#444466')

style(ax1, 'Phase Currents vs Reference', 'Current (A)')
style(ax2, 'Current Error  (ref − measured)', 'Error (A)')
style(ax3, 'Switch States', 'State')

ax1.set_ylim(-YLIM_I, YLIM_I)
ax2.set_ylim(-YLIM_I/2, YLIM_I/2)
ax3.set_ylim(-0.2, 1.5)
ax3.set_yticks([0, 1])
ax3.set_yticklabels(['OFF', 'ON'], color='white')
ax3.set_xlabel('Samples', color='white', fontsize=9)

# Hysteresis band lines on error plot
ax2.axhline( HYST_B, color='yellow', lw=0.8, linestyle='--', alpha=0.7, label=f'+band ({HYST_B}A)')
ax2.axhline(-HYST_B, color='yellow', lw=0.8, linestyle='--', alpha=0.7, label=f'-band ({HYST_B}A)')

# Lines — plot 1
lm1, = ax1.plot([], [], color='#00bfff', lw=1.5, label='Phase A meas')
lm2, = ax1.plot([], [], color='#ff4444', lw=1.5, label='Phase B meas')
lm3, = ax1.plot([], [], color='#44ff88', lw=1.5, label='Phase C est')
lr1, = ax1.plot([], [], color='white',   lw=1.0, ls='--', label='Ref A')
lr2, = ax1.plot([], [], color='#ffaaaa', lw=1.0, ls='--', label='Ref B')
lr3, = ax1.plot([], [], color='#aaffcc', lw=1.0, ls='--', label='Ref C')
ax1.legend(loc='upper right', fontsize=7,
           facecolor='#1a1a2e', labelcolor='white', ncol=3)

# Lines — plot 2
le1, = ax2.plot([], [], color='#00bfff', lw=1.2, label='Error A')
le2, = ax2.plot([], [], color='#ff4444', lw=1.2, label='Error B')
le3, = ax2.plot([], [], color='#44ff88', lw=1.2, label='Error C')
ax2.legend(loc='upper right', fontsize=7,
           facecolor='#1a1a2e', labelcolor='white')

# Lines — plot 3
ls1, = ax3.plot([], [], color='#00bfff', lw=1.2, label='SW A  (PB7)')
ls2, = ax3.plot([], [], color='#ff4444', lw=1.2, label='SW B  (PB8)')
ls3, = ax3.plot([], [], color='#44ff88', lw=1.2, label='SW C  (PB9)')
ax3.legend(loc='upper right', fontsize=7,
           facecolor='#1a1a2e', labelcolor='white')

# Live stats text
stats = ax1.text(0.01, 0.97, '', transform=ax1.transAxes,
                 fontsize=8, color='white', va='top',
                 fontfamily='monospace',
                 bbox=dict(facecolor='#0d0d1a', alpha=0.8))

# ── Update ───────────────────────────────
def update(frame):
    if ser and ser.in_waiting:
        try:
            raw  = ser.readline().decode('ascii', errors='ignore').strip()
            p    = raw.split(',')
            if len(p) == 7:
                m1 = float(p[0]) / 1000.0
                m2 = float(p[1]) / 1000.0
                m3 = float(p[2]) / 1000.0
                r1 = float(p[3]) / 1000.0
                s1 = float(p[4])
                s2 = float(p[5])
                s3 = float(p[6])

                # estimate ref B and C from ref A phase angle
                # (they are sent as 0 from STM32 — derive here)
                buf['m1'].append(m1);  buf['m2'].append(m2)
                buf['m3'].append(m3);  buf['r1'].append(r1)
                buf['e1'].append(r1 - m1)
                buf['e2'].append(-r1/2 - m2)   # approx ref B = -ref/2 (120deg)
                buf['e3'].append(-r1/2 - m3)   # approx ref C
                buf['s1'].append(s1)
                buf['s2'].append(s2 + 0.02)    # small offset so lines don't overlap
                buf['s3'].append(s3 + 0.04)
        except Exception:
            pass

    lm1.set_data(x, list(buf['m1']))
    lm2.set_data(x, list(buf['m2']))
    lm3.set_data(x, list(buf['m3']))
    lr1.set_data(x, list(buf['r1']))

    le1.set_data(x, list(buf['e1']))
    le2.set_data(x, list(buf['e2']))
    le3.set_data(x, list(buf['e3']))

    ls1.set_data(x, list(buf['s1']))
    ls2.set_data(x, list(buf['s2']))
    ls3.set_data(x, list(buf['s3']))

    # Stats
    m1v = buf['m1'][-1]; m2v = buf['m2'][-1]; m3v = buf['m3'][-1]
    r1v = buf['r1'][-1]
    stats.set_text(
        f"A: {m1v:+.3f}A   B: {m2v:+.3f}A   C: {m3v:+.3f}A   "
        f"Ref: {r1v:+.3f}A   "
        f"Err A: {r1v-m1v:+.3f}A"
    )

    return (lm1, lm2, lm3, lr1,
            le1, le2, le3,
            ls1, ls2, ls3, stats)

ani = animation.FuncAnimation(
    fig, update, interval=40,
    blit=True, cache_frame_data=False)

plt.tight_layout()
plt.show()

if ser:
    ser.close()
    print("[OK] Serial closed.")