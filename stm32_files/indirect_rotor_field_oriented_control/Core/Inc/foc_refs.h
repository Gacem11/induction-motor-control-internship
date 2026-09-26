#ifndef FOC_REFS_H
#define FOC_REFS_H

void FluxTorque_To_FOC_Refs(float flux_ref, float torque_ref,
                             float *id_ref, float *iq_ref, float *omega_slip);

#endif
