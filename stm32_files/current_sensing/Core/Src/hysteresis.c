#include "hysteresis.h"

uint8_t switch_A = 0;
uint8_t switch_B = 0;
uint8_t switch_C = 0;

float i_ref_a = 0.0f;
float i_ref_b = 0.0f;
float i_ref_c = 0.0f;

void Hysteresis_Init(void)
{
    switch_A = 0;
    switch_B = 0;
    switch_C = 0;

    CLR_PHASE_A();
    CLR_PHASE_B();
    CLR_PHASE_C();
}

void Hysteresis_Update(float i_a, float i_b, float i_c)
{
    // ── Phase A ───────────────────────────
    float err_a = i_ref_a - i_a;
    if(err_a > +HYST_BAND)
    {
        switch_A = 1;
        SET_PHASE_A();
    }
    else if(err_a < -HYST_BAND)
    {
        switch_A = 0;
        CLR_PHASE_A();
    }

    // ── Phase B ───────────────────────────
    float err_b = i_ref_b - i_b;
    if(err_b > +HYST_BAND)
    {
        switch_B = 1;
        SET_PHASE_B();
    }
    else if(err_b < -HYST_BAND)
    {
        switch_B = 0;
        CLR_PHASE_B();
    }

    // ── Phase C ───────────────────────────
    // In 3 phase: ic = -(ia + ib) by Kirchhoff
    // so we calculate ic from ia and ib
    // no third sensor needed
    float err_c = i_ref_c - i_c;
    if(err_c > +HYST_BAND)
    {
        switch_C = 1;
        SET_PHASE_C();
    }
    else if(err_c < -HYST_BAND)
    {
        switch_C = 0;
        CLR_PHASE_C();
    }
}
