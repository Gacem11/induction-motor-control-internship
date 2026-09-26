#include "control.h"
#include "transform.h"
#include "angle.h"
#include "foc_refs.h"

/* ── Exported variables ──────────────────────────────────────── */
volatile float   i_meas_1   = 0.0f;
volatile float   i_meas_2   = 0.0f;
volatile float   i_meas_3   = 0.0f;
volatile float   i_ref_1    = 0.0f;
volatile float   i_ref_2    = 0.0f;
volatile float   i_ref_3    = 0.0f;
volatile float   i_dq_d     = 0.0f;   // Id reference, exported for logging
volatile float   i_dq_q     = 0.0f;   // Iq reference, exported for logging
volatile float   theta_e    = 0.0f;   // electrical angle, exported for logging
volatile uint8_t sw1        = 0;
volatile uint8_t sw2        = 0;
volatile uint8_t sw3        = 0;
volatile uint8_t data_ready = 0;

/* Flux/torque references — refrence_torque gets overwritten from main.c (speed loop) */
volatile float refrence_flux   = 0.9f;
volatile float refrence_torque = 10.0f;

extern volatile float rpm_filtered;

/* ── Private variables ───────────────────────────────────────── */
static ADC_HandleTypeDef *_hadc1;
static float filt_1 = 0.0f;
static float filt_2 = 0.0f;

/* ── Control_Init ────────────────────────────────────────────── */
void Control_Init(ADC_HandleTypeDef *hadc1,
                  TIM_HandleTypeDef *htim3)
{
    _hadc1 = hadc1;

    /* Calibrate ADC */
    HAL_ADCEx_Calibration_Start(_hadc1, ADC_SINGLE_ENDED);
    HAL_Delay(10);

    /* Safe state — all upper switches OFF */
    HAL_GPIO_WritePin(SW_PORT, SW1_PIN | SW2_PIN | SW3_PIN, GPIO_PIN_RESET);

    /* Start injected ADC */
    HAL_ADCEx_InjectedStart_IT(_hadc1);

    /* Start TIM3 — triggers ADC at CONTROL_FS_HZ */
    HAL_TIM_Base_Start(htim3);
}

/* ── ADC callback — runs at 20 kHz ──────────────────────────── */
void HAL_ADCEx_InjectedConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance != ADC1) return;

    /* 1. Read ADC and convert to amps */
    uint32_t raw1 = HAL_ADCEx_InjectedGetValue(_hadc1, ADC_INJECTED_RANK_1);
    uint32_t raw2 = HAL_ADCEx_InjectedGetValue(_hadc1, ADC_INJECTED_RANK_2);

    float V1 = (raw1 * 3.3f) / 4095.0f;
    float V2 = (raw2 * 3.3f) / 4095.0f;

    float i1 = (V1 - OFFSET_1) / SENSITIVITY_1;
    float i2 = (V2 - OFFSET_2) / SENSITIVITY_2;

    /* 2. Low-pass filter */
    filt_1 = FILTER_ALPHA * i1 + (1.0f - FILTER_ALPHA) * filt_1;
    filt_2 = FILTER_ALPHA * i2 + (1.0f - FILTER_ALPHA) * filt_2;

    /* 3. Store measurements — Phase C estimated */
    i_meas_1 = filt_1;
    i_meas_2 = filt_2;
    i_meas_3 = -(filt_1 + filt_2);

    /* 4. IRFOC reference generation */
    float id_ref, iq_ref, omega_slip;
    FluxTorque_To_FOC_Refs(refrence_flux, refrence_torque, &id_ref, &iq_ref, &omega_slip);

    i_dq_d = id_ref;
    i_dq_q = iq_ref;

    theta_e = Angle_Update(rpm_filtered, omega_slip);

    dq_to_abc(id_ref, iq_ref, theta_e, (float*)&i_ref_1, (float*)&i_ref_2, (float*)&i_ref_3);

    /* 5. Hysteresis comparator → GPIO */
    if (i_meas_1 > i_ref_1 + HYST_BAND)
    {   sw1 = 0; HAL_GPIO_WritePin(SW_PORT, SW1_PIN, GPIO_PIN_RESET); }
    else if (i_meas_1 < i_ref_1 - HYST_BAND)
    {   sw1 = 1; HAL_GPIO_WritePin(SW_PORT, SW1_PIN, GPIO_PIN_SET);   }

    if (i_meas_2 > i_ref_2 + HYST_BAND)
    {   sw2 = 0; HAL_GPIO_WritePin(SW_PORT, SW2_PIN, GPIO_PIN_RESET); }
    else if (i_meas_2 < i_ref_2 - HYST_BAND)
    {   sw2 = 1; HAL_GPIO_WritePin(SW_PORT, SW2_PIN, GPIO_PIN_SET);   }

    if (i_meas_3 > i_ref_3 + HYST_BAND)
    {   sw3 = 0; HAL_GPIO_WritePin(SW_PORT, SW3_PIN, GPIO_PIN_RESET); }
    else if (i_meas_3 < i_ref_3 - HYST_BAND)
    {   sw3 = 1; HAL_GPIO_WritePin(SW_PORT, SW3_PIN, GPIO_PIN_SET);   }

    /* 6. Flag for UART logging (decimated to 2kHz so it doesn't flood UART) */
    static uint16_t print_div = 0;
    if (++print_div >= 10)
    {
        print_div = 0;
        data_ready = 1;
    }
}
