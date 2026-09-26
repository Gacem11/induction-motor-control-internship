#include "transform.h"
#include <math.h>

void abc_to_dq(float ia, float ib, float ic, float theta_e, float *id, float *iq)
{
    /* Clarke transform: abc -> alpha-beta */
    float ialpha = ia;
    float ibeta  = (ia + 2.0f*ib) / sqrtf(3.0f);

    /* Park transform: alpha-beta -> dq */
    float c = cosf(theta_e);
    float s = sinf(theta_e);

    *id =  ialpha*c + ibeta*s;
    *iq = -ialpha*s + ibeta*c;
}

void dq_to_abc(float id, float iq, float theta_e, float *ia, float *ib, float *ic)
{
    /* Inverse Park: dq -> alpha-beta */
    float c = cosf(theta_e);
    float s = sinf(theta_e);

    float ialpha = id*c - iq*s;
    float ibeta  = id*s + iq*c;

    /* Inverse Clarke: alpha-beta -> abc */
    *ia = ialpha;
    *ib = -0.5f*ialpha + (sqrtf(3.0f)/2.0f)*ibeta;
    *ic = -0.5f*ialpha - (sqrtf(3.0f)/2.0f)*ibeta;
}
