#ifndef SPEED_H
#define SPEED_H

#include "stm32g4xx_hal.h"

/* ── Configuration ────────────────────────────────────────────
   Adjust these to match your setup */
#define EDGES_PER_REV     6.0f          /* IR sensor: 6 rising edges = 1 revolution */
#define TIM2_CLK_HZ       170000000.0f  /* TIM2 counting clock, no prescale */
#define MAX_RPM           1700.0f       /* sanity ceiling -- discard readings above this */
#define MIN_VALID_TICKS   666U          /* below this = noise/bounce, ignore capture */
#define RPM_EMA_ALPHA     0.03f          /* stage 1 low-pass strength: lower = smoother/slower, higher = faster/noisier */
#define RPM_EMA_ALPHA2    0.15f          /* stage 2 low-pass strength, applied after stage 1 -- same tuning rule */

#define IR_THRESHOLD_DAC_CODE   1985    /* DAC code (0-4095) setting comparator threshold */

/* ── Exported variables ──────────────────────────────────────── */
extern volatile float motor_rpm;        /* raw RPM from latest edge-to-edge period */
extern volatile float rpm_filtered;      /* median + moving-average filtered RPM */

/* ── Public API ──────────────────────────────────────────────── */
void Speed_Init(DAC_HandleTypeDef *hdac, TIM_HandleTypeDef *htim2);

/* Call periodically (e.g. every 500ms) from main loop: if no new edge
   has arrived recently, this zeroes the RPM (motor considered stopped) */
void Speed_CheckTimeout(void);

#endif
