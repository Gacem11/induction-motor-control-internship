#include "angle.h"
#include <math.h>

#define POLE_PAIRS  2.0f
#define DT          0.00005f     /* 50us, fixed ISR period */
#define TWO_PI      6.28318530718f

static float theta_e = 0.0f;

void Angle_Reset(void)
{
    theta_e = 0.0f;
}

float Angle_Update(float rpm, float omega_slip)
{
    float omega_mech_elec = (rpm / 9.55f) * POLE_PAIRS;
    float omega_e = omega_mech_elec + omega_slip;

    theta_e += omega_e * DT;

    /* wrap to [0, 2*pi) */
    if (theta_e >= TWO_PI) theta_e -= TWO_PI;
    if (theta_e < 0.0f)    theta_e += TWO_PI;

    return theta_e;
}
