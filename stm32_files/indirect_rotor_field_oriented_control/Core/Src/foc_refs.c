#include "foc_refs.h"

#define LM  0.31f
#define LR  0.32106f   /* Lm + Llr */
#define P   2.0f       /* pole pairs */
#define TR  0.1672f    /* rotor time constant */

void FluxTorque_To_FOC_Refs(float flux_ref, float torque_ref,
                             float *id_ref, float *iq_ref, float *omega_slip)
{
    *id_ref     = flux_ref / LM;
    *iq_ref     = torque_ref * (2.0f * LR) / (3.0f * P * LM * flux_ref);
    *omega_slip = (LM / TR) * (*iq_ref) / flux_ref;
}
