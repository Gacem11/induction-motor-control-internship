#ifndef CONTROL_H
#define CONTROL_H

#include "stm32g4xx_hal.h"
#include <math.h>


extern volatile float i_dq_d;
extern volatile float i_dq_q;
extern volatile float refrence_torque;



/* ── Current sensor calibration ─────────────────────────────── */
#define OFFSET_1        1.797f
#define SENSITIVITY_1   0.100608f
#define OFFSET_2        1.725f
#define SENSITIVITY_2   0.100130f

/* ── Low-pass filter ─────────────────────────────────────────── */
#define FILTER_ALPHA    0.1f

/* ── Reference current ─────────────────────────────────────── */
#define I_REF_AMPLITUDE  2.6f
#define I_REF_FREQ_HZ    20.0f
#define CONTROL_FS_HZ    20000.0f

/* ── Hysteresis band ─────────────────────────────────────────── */
#define HYST_BAND        0.2f

/* ── GPIO upper switches  PB7 / PB8 / PB9 ───────────────────── */
#define SW_PORT          GPIOB
#define SW1_PIN          GPIO_PIN_7
#define SW2_PIN          GPIO_PIN_8
#define SW3_PIN          GPIO_PIN_9

/* ── Exported variables ──────────────────────────────────────── */
extern volatile float   i_meas_1;
extern volatile float   i_meas_2;
extern volatile float   i_meas_3;
extern volatile float   i_ref_1;
extern volatile float   i_ref_2;
extern volatile float   i_ref_3;
extern volatile uint8_t sw1;
extern volatile uint8_t sw2;
extern volatile uint8_t sw3;
extern volatile uint8_t data_ready;

/* ── Public API ──────────────────────────────────────────────── */
void Control_Init(ADC_HandleTypeDef *hadc1,
                  TIM_HandleTypeDef *htim3);

#endif /* CONTROL_H */
