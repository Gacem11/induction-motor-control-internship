#include "speed.h"

/* ── Exported ─────────────────────────────────────────────── */
volatile float motor_rpm    = 0.0f;
volatile float rpm_filtered = 0.0f;

/* ── Private ──────────────────────────────────────────────── */
static TIM_HandleTypeDef *_htim2;

static uint32_t capture1        = 0;
static uint32_t capture2        = 0;
static uint32_t difference      = 0;
static uint8_t  first_capture   = 0;
static uint32_t last_capture_time = 0;

/* stage 1 output feeds into stage 2 (rpm_filtered) -- this is the
   only extra state a second cascade stage needs */
static float rpm_stage1 = 0.0f;

/* ── Init ─────────────────────────────────────────────────── */
void Speed_Init(DAC_HandleTypeDef *hdac, TIM_HandleTypeDef *htim2)
{
    _htim2 = htim2;

    /* Set the comparator threshold via DAC */
    HAL_DAC_Start(hdac, DAC_CHANNEL_1);
    HAL_DAC_SetValue(hdac, DAC_CHANNEL_1, DAC_ALIGN_12B_R, IR_THRESHOLD_DAC_CODE);

    /* Start the comparator itself -- handle name depends on your CubeMX
       instance, adjust hcomp1 to match your project (declared in comp.h) */


    /* Start input capture on TIM2 channel 1 */
    HAL_TIM_IC_Start_IT(_htim2, TIM_CHANNEL_1);

    /* Priority: below ADC (0) and any current-control ISR, above UART (3) */
    HAL_NVIC_SetPriority(TIM2_IRQn, 2, 0);

    last_capture_time = HAL_GetTick();
}

/* ── Two-stage low-pass (cascaded EMA) filter, with basic ceiling
   rejection ──────────────────────────────────────────────────
   Stage 1 smooths the raw reading, then stage 2 smooths stage 1's
   output again. Cascading two simple filters like this rolls off
   noise much harder than one stage alone, so it settles flatter --
   at the cost of a bit more lag than a single stage. */
static float RPM_Filter(float new_rpm)
{
    if (new_rpm >= MAX_RPM)
        return rpm_filtered;   /* implausible reading -- ignore, keep last value */

    rpm_stage1   = rpm_stage1   + RPM_EMA_ALPHA  * (new_rpm    - rpm_stage1);
    rpm_filtered = rpm_filtered + RPM_EMA_ALPHA2 * (rpm_stage1 - rpm_filtered);
    return rpm_filtered;
}

/* ── Input capture callback -- fires on every rising edge ────── */
void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance != TIM2) return;

    if (first_capture == 0)
    {
        capture1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
        first_capture = 1;
    }
    else
    {
        capture2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);

        if (capture2 >= capture1)
            difference = capture2 - capture1;
        else
            difference = (0xFFFFFFFFu - capture1) + capture2 + 1u;  /* handle timer wraparound */

        if (difference < MIN_VALID_TICKS)
        {
            /* too fast to be real -- likely noise/bounce, discard and
               wait for the next edge without resetting the reference point */
            first_capture = 0;
            return;
        }

        if (difference != 0)
        {
            /* time between edges -> edge frequency -> RPM
               freq = ticks-per-second / ticks-between-edges
               RPM  = (freq / edges-per-rev) * 60 seconds */
            float freq = TIM2_CLK_HZ / (float)difference;
            motor_rpm  = (freq * 4.5);

            if (motor_rpm > MAX_RPM) motor_rpm = MAX_RPM;

            RPM_Filter(motor_rpm);
        }

        first_capture = 0;
    }

    last_capture_time = HAL_GetTick();
}

/* ── Call from main loop periodically ────────────────────────── */
void Speed_CheckTimeout(void)
{
    if (HAL_GetTick() - last_capture_time > 500)
    {
        if (motor_rpm > 0.0f)
        {
            motor_rpm     = 0.0f;
            rpm_filtered  = 0.0f;
            rpm_stage1    = 0.0f;
            first_capture = 0;
        }
    }
}
