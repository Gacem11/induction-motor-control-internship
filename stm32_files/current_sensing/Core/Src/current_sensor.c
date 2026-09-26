#include "current_sensor.h"

float    current_1 = 0.0f;
float    current_2 = 0.0f;
uint32_t adc1_raw  = 0;
uint32_t adc2_raw  = 0;

float    buffer_1[BUFFER_SIZE];
float    buffer_2[BUFFER_SIZE];
uint16_t buf_index = 0;
uint8_t  buf_full  = 0;

volatile uint8_t  adc1_done = 0;
volatile uint8_t  adc2_done = 0;
volatile uint8_t  foc_ready = 0;

static ADC_HandleTypeDef *_hadc1;
static ADC_HandleTypeDef *_hadc2;

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if(hadc->Instance == ADC1)
    {
        adc1_raw  = HAL_ADC_GetValue(hadc);
        adc1_done = 1;
    }
    if(hadc->Instance == ADC2)
    {
        adc2_raw  = HAL_ADC_GetValue(hadc);
        adc2_done = 1;
    }
}

void CurrentSensor_Init(ADC_HandleTypeDef *hadc1,
                        ADC_HandleTypeDef *hadc2)
{
    _hadc1 = hadc1;
    _hadc2 = hadc2;
    HAL_ADCEx_Calibration_Start(_hadc1, ADC_SINGLE_ENDED);
    HAL_ADCEx_Calibration_Start(_hadc2, ADC_SINGLE_ENDED);
    HAL_Delay(10);
}

float current_1_filtered = 0.0f;
float current_2_filtered = 0.0f;

void Read_Currents(void)
{
    // read sensor 1
    adc1_done = 0;
    HAL_ADC_Start_IT(_hadc1);
    while(adc1_done == 0);
    HAL_ADC_Stop_IT(_hadc1);

    // read sensor 2
    adc2_done = 0;
    HAL_ADC_Start_IT(_hadc2);
    while(adc2_done == 0);
    HAL_ADC_Stop_IT(_hadc2);

    // convert to Amperes
    float V1  = (adc1_raw * 3.3f) / 4095.0f;
    float V2  = (adc2_raw * 3.3f) / 4095.0f;
    current_1 = (V1 - OFFSET_1) / SENSITIVITY_1;
    current_2 = (V2 - OFFSET_2) / SENSITIVITY_2;

    // IIR low pass filter
    // y[n] = alpha * x[n] + (1-alpha) * y[n-1]
    // new = alpha×new_raw + (1-alpha)×previous
    current_1_filtered = FILTER_ALPHA * current_1
                       + (1.0f - FILTER_ALPHA) * current_1_filtered;

    current_2_filtered = FILTER_ALPHA * current_2
                       + (1.0f - FILTER_ALPHA) * current_2_filtered;

    // store filtered values in buffer
    if(buf_index < BUFFER_SIZE)
    {
        buffer_1[buf_index] = current_1_filtered;
        buffer_2[buf_index] = current_2_filtered;
        buf_index++;
    }
    else
    {
        buf_full  = 1;
        buf_index = 0;
    }
}
