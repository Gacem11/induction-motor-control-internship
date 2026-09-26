#ifndef CURRENT_SENSOR_H
#define CURRENT_SENSOR_H
#define FILTER_ALPHA   0.3f

extern float current_1_filtered;
extern float current_2_filtered;

#include "stm32g4xx_hal.h"
void Read_Currents(void);
#define OFFSET_1       1.886f
#define SENSITIVITY_1  0.104f

#define OFFSET_2       1.75f    // tune later
#define SENSITIVITY_2  0.105f   // tune later

#define BUFFER_SIZE    500

extern float    current_1;
extern float    current_2;
extern uint32_t adc1_raw;
extern uint32_t adc2_raw;
extern float    buffer_1[BUFFER_SIZE];
extern float    buffer_2[BUFFER_SIZE];
extern uint16_t buf_index;
extern uint8_t  buf_full;

// flag set in interrupt — FOC runs when this = 1
extern volatile uint8_t foc_ready;

void CurrentSensor_Init(ADC_HandleTypeDef *hadc1,
                        ADC_HandleTypeDef *hadc2);

#endif
