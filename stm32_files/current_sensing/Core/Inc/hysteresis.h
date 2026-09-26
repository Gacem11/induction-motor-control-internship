#ifndef HYSTERESIS_H
#define HYSTERESIS_H

#include "stm32g4xx_hal.h"

// ═══════════════════════════════
// Hysteresis band
// ±0.2A = switch fires when
// error exceeds 0.2A
#define HYST_BAND   0.2f
// ═══════════════════════════════

// Fast GPIO macros
#define SET_PHASE_A()   GPIOB->BSRR = GPIO_PIN_7
#define SET_PHASE_B()   GPIOB->BSRR = GPIO_PIN_8
#define SET_PHASE_C()   GPIOB->BSRR = GPIO_PIN_9

#define CLR_PHASE_A()   GPIOB->BRR  = GPIO_PIN_7
#define CLR_PHASE_B()   GPIOB->BRR  = GPIO_PIN_8
#define CLR_PHASE_C()   GPIOB->BRR  = GPIO_PIN_9

// switch states — readable in debugger
extern uint8_t switch_A;
extern uint8_t switch_B;
extern uint8_t switch_C;

// reference currents
extern float i_ref_a;
extern float i_ref_b;
extern float i_ref_c;

void Hysteresis_Init(void);
void Hysteresis_Update(float i_a, float i_b, float i_c);

#endif
