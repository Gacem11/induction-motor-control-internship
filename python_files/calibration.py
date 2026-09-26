"""
3-Phase Current Calibration Tool
────────────────────────────────
Calibrates Phase A and Phase B only.
Phase C is estimated (Ia + Ib + Ic = 0), no slider needed.

Starting point = values already in your STM32 control.h:
    OFFSET_1 = 1.65f,  SENSITIVITY_1 = 0.104f
    OFFSET_2 = 1.65f,  SENSITIVITY_2 = 0.104f

The sliders apply a SOFTWARE correction on top of what the STM32
already computed. When you are happy, read the yellow box and copy
the NEW #define values into control.h.
"""

import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Slider, Button
from collections import deque
import numpy as np

# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────
PORT        = 'COM4'
BAUD        = 115200
POINTS      = 100       # samples visible on screen
INTERVAL_MS = 100       # 100 ms refresh  →  10 fps  (readable)

# Your current STM32 values (starting point)
STM_OFFSET_1      = 1.65      # volts
STM_SENSITIVITY_1 = 0.104     # V/A
STM_OFFSET_2      = 1.65
STM_SENSITIVITY_2 = 0.104

# ─────────────────────────────────────────────────────────────
# SERIAL
# ─────────────────────────────────────────────────────────────
try:
    ser = serial.Serial(PORT, BAUD, timeout=0.01)
    print(f"[OK] Serial open on {PORT}")
except Exception as e:
    print(f"[ERROR] Cannot open {PORT}: {e}")
    ser = None

# ─────────────────────────────────────────────────────────────
# DATA BUFFERS
# ─────────────────────────────────────────────────────────────
data = {k: deque([0.0]*POINTS, maxlen=POINTS)
        for k in ['A', 'B', 'C', 'ref']}
sw_state = [0, 0, 0]
x = np.arange(POINTS)

# Software calibration correction on top of STM32 values
# Final_current = (raw_current + offset_correction) * gain_correction
cal = {
    'offset_A': 0.0,  'gain_A': 1.0,
    'offset_B': 0.0,  'gain_B': 1.0,
}

# ─────────────────────────────────────────────────────────────
# FIGURE
# ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 9))
fig.patch.set_facecolor('#1a1a2e')
fig.suptitle("Current Calibration  –  Phase A & B  (C estimated)",
             fontsize=15, color='white', fontweight='bold', y=0.98)

# ── Waveform area: 2 rows x 2 cols ──────────────────────────
gs = gridspec.GridSpec(2, 2,
                       left=0.07, right=0.97,
                       top=0.93,  bottom=0.42,
                       hspace=0.25, wspace=0.25)

colors = {'A':   '#00bfff',
          'B':   '#ff4444',
          'C':   '#44ff88',
          'ref': '#ffff00'}
titles = {'A':   'Phase A  (measured + calibrated)',
          'B':   'Phase B  (measured + calibrated)',
          'C':   'Phase C  (estimated = -(A+B))',
          'ref': 'Reference  Ia_ref'}

axes  = {}
lines = {}
for i, key in enumerate(['A', 'B', 'C', 'ref']):
    row, col = divmod(i, 2)
    ax = fig.add_subplot(gs[row, col])
    ax.set_facecolor('#0d0d1a')
    ax.set_xlim(0, POINTS)
    ax.set_ylim(-8, 8)
    ax.axhline(0, color='white', lw=0.5, alpha=0.4)
    ax.grid(True, color='#333355', lw=0.5)
    ax.tick_params(colors='white', labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor('#444466')
    ax.set_ylabel("A", color='white', fontsize=8)
    ax.set_title(titles[key], color=colors[key], fontsize=9, fontweight='bold')
    ln, = ax.plot(x, np.zeros(POINTS), color=colors[key], lw=1.8)
    axes[key]  = ax
    lines[key] = ln

# ── Stats row ────────────────────────────────────────────────
gs_stats = gridspec.GridSpec(1, 4,
                             left=0.07, right=0.97,
                             top=0.40,  bottom=0.32,
                             wspace=0.05)
stat_texts = {}
for i, key in enumerate(['A', 'B', 'C', 'ref']):
    ax = fig.add_subplot(gs_stats[0, i])
    ax.set_facecolor('#0d0d1a')
    ax.axis('off')
    txt = ax.text(0.03, 0.97, "", transform=ax.transAxes,
                  fontsize=8, color=colors[key],
                  verticalalignment='top', fontfamily='monospace')
    stat_texts[key] = txt

# ── SW indicators ────────────────────────────────────────────
ax_sw = fig.add_axes([0.82, 0.32, 0.15, 0.07])
ax_sw.set_facecolor('#0d0d1a')
ax_sw.axis('off')
sw_circles = []
for j, name in enumerate(['SW1', 'SW2', 'SW3']):
    c = plt.Circle((0.15 + j*0.33, 0.55), 0.13, color='#333333')
    ax_sw.add_patch(c)
    ax_sw.text(0.15 + j*0.33, 0.05, name,
               ha='center', fontsize=7, color='white')
    sw_circles.append(c)
ax_sw.set_xlim(0, 1)
ax_sw.set_ylim(0, 1)

# ─────────────────────────────────────────────────────────────
# SLIDERS  (only A and B)
# ─────────────────────────────────────────────────────────────
#   label           left    bot    key          min    max   init
slider_defs = [
    ('Offset A (A)', 0.07,  0.27, 'offset_A', -2.0,  2.0,  0.0),
    ('Gain A',       0.07,  0.22, 'gain_A',    0.5,  2.0,  1.0),
    ('Offset B (A)', 0.55,  0.27, 'offset_B', -2.0,  2.0,  0.0),
    ('Gain B',       0.55,  0.22, 'gain_B',    0.5,  2.0,  1.0),
]

sliders = {}
for (lbl, l, b, key, vmin, vmax, vinit) in slider_defs:
    ax_sl = fig.add_axes([l, b, 0.38, 0.025], facecolor='#2a2a4a')
    sl = Slider(ax_sl, lbl, vmin, vmax, valinit=vinit,
                color='#4444aa', track_color='#222244')
    sl.label.set_color('white');      sl.label.set_fontsize(9)
    sl.valtext.set_color('#aaaaff');  sl.valtext.set_fontsize(9)
    sliders[key] = sl

def update_cal(val):
    for k, sl in sliders.items():
        cal[k] = sl.val

for sl in sliders.values():
    sl.on_changed(update_cal)

# ─────────────────────────────────────────────────────────────
# LIVE VALUES PANEL  (green = current software correction)
# ─────────────────────────────────────────────────────────────
ax_live = fig.add_axes([0.07, 0.10, 0.38, 0.10])
ax_live.set_facecolor('#0a0a15')
ax_live.axis('off')
ax_live.set_title("  Software correction applied now",
                  color='#88ff88', fontsize=8, loc='left', pad=3)
live_text = ax_live.text(0.02, 0.85, "",
                         transform=ax_live.transAxes,
                         fontsize=9, color='#88ff88',
                         verticalalignment='top',
                         fontfamily='monospace')

# ─────────────────────────────────────────────────────────────
# DEFINES PANEL  (yellow = what to paste into control.h)
# ─────────────────────────────────────────────────────────────
ax_def = fig.add_axes([0.55, 0.04, 0.38, 0.16])
ax_def.set_facecolor('#0a0a15')
ax_def.axis('off')
ax_def.set_title("  ► Copy these into control.h",
                 color='#ffaa44', fontsize=9, loc='left', pad=3)
def_text = ax_def.text(0.02, 0.88, "",
                       transform=ax_def.transAxes,
                       fontsize=9, color='#ffdd88',
                       verticalalignment='top',
                       fontfamily='monospace')

# ─────────────────────────────────────────────────────────────
# BUTTONS
# ─────────────────────────────────────────────────────────────
ax_breset = fig.add_axes([0.07, 0.04, 0.13, 0.04])
btn_reset  = Button(ax_breset, 'Reset Sliders',
                    color='#222244', hovercolor='#4444aa')
btn_reset.label.set_color('white')
btn_reset.on_clicked(lambda e: [sl.reset() for sl in sliders.values()])

ax_bprint = fig.add_axes([0.22, 0.04, 0.13, 0.04])
btn_print  = Button(ax_bprint, 'Print to Terminal',
                    color='#222244', hovercolor='#4444aa')
btn_print.label.set_color('white')

def print_to_terminal(event):
    new_off1, new_sen1, new_off2, new_sen2 = compute_defines()
    print("\n══════ Copy into control.h ══════")
    print(f"#define OFFSET_1       {new_off1:.5f}f")
    print(f"#define SENSITIVITY_1  {new_sen1:.6f}f")
    print(f"#define OFFSET_2       {new_off2:.5f}f")
    print(f"#define SENSITIVITY_2  {new_sen2:.6f}f")
    print("═════════════════════════════════\n")

btn_print.on_clicked(print_to_terminal)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def apply_cal(raw, offset, gain):
    return (raw + offset) * gain

def rms(arr):
    return float(np.sqrt(np.mean(np.square(arr))))

def compute_defines():
    """
    The STM32 computes:  i = (adc_volts - OFFSET) / SENSITIVITY
    After calibration we want:
        i_corrected = (i_raw + offset_corr) * gain_corr
                    = ((adc_volts - OFFSET)/SENS + offset_corr) * gain_corr

    Equivalent new defines:
        new_SENSITIVITY = SENSITIVITY / gain_corr
        new_OFFSET      = OFFSET - offset_corr * SENSITIVITY
    """
    new_off1 = STM_OFFSET_1 - cal['offset_A'] * STM_SENSITIVITY_1
    new_sen1 = STM_SENSITIVITY_1 / cal['gain_A']
    new_off2 = STM_OFFSET_2 - cal['offset_B'] * STM_SENSITIVITY_2
    new_sen2 = STM_SENSITIVITY_2 / cal['gain_B']
    return new_off1, new_sen1, new_off2, new_sen2

# ─────────────────────────────────────────────────────────────
# ANIMATION UPDATE
# ─────────────────────────────────────────────────────────────
def update(frame):
    global sw_state

    if ser and ser.in_waiting:
        try:
            raw_line = ser.readline().decode('ascii', errors='ignore').strip()
            parts = raw_line.split(',')
            if len(parts) == 7:
                ia_raw  = float(parts[0]) / 1000.0
                ib_raw  = float(parts[1]) / 1000.0
                ref     = float(parts[3]) / 1000.0
                sw_state = [int(parts[4]), int(parts[5]), int(parts[6])]

                ia = apply_cal(ia_raw, cal['offset_A'], cal['gain_A'])
                ib = apply_cal(ib_raw, cal['offset_B'], cal['gain_B'])
                ic = -(ia + ib)          # Kirchhoff: Ia+Ib+Ic = 0

                data['A'].append(ia)
                data['B'].append(ib)
                data['C'].append(ic)
                data['ref'].append(ref)
        except Exception:
            pass

    # Waveforms + stats
    for key in ['A', 'B', 'C', 'ref']:
        y = np.array(data[key])
        lines[key].set_ydata(y)
        ymax = max(abs(y.max()), abs(y.min()), 0.5)
        axes[key].set_ylim(-ymax * 1.3, ymax * 1.3)

        r    = rms(y)
        mx   = float(y.max())
        mn   = float(y.min())
        mean = float(y.mean())
        stat_texts[key].set_text(
            f"RMS  : {r:+7.3f} A\n"
            f"MAX  : {mx:+7.3f} A\n"
            f"MIN  : {mn:+7.3f} A\n"
            f"P-P  : {mx-mn:7.3f} A\n"
            f"MEAN : {mean:+7.3f} A"
        )

    # SW indicators
    for j, state in enumerate(sw_state):
        sw_circles[j].set_color('#00ff44' if state else '#333333')

    # Live correction panel
    live_text.set_text(
        f"Phase A :  offset = {cal['offset_A']:+.4f} A    gain = {cal['gain_A']:.4f}\n"
        f"Phase B :  offset = {cal['offset_B']:+.4f} A    gain = {cal['gain_B']:.4f}"
    )

    # Defines panel — updated live
    no1, ns1, no2, ns2 = compute_defines()
    def_text.set_text(
        f"#define OFFSET_1       {no1:.5f}f\n"
        f"#define SENSITIVITY_1  {ns1:.6f}f\n"
        f"\n"
        f"#define OFFSET_2       {no2:.5f}f\n"
        f"#define SENSITIVITY_2  {ns2:.6f}f"
    )

    return list(lines.values()) + list(stat_texts.values()) + sw_circles

# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
ani = animation.FuncAnimation(
    fig, update,
    interval=INTERVAL_MS,
    blit=False,
    cache_frame_data=False
)

plt.show()

if ser:
    ser.close()
    print("[OK] Serial closed.")