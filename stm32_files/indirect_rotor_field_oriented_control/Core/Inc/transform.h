#ifndef TRANSFORMS_H
#define TRANSFORMS_H

/* Clarke + Park: 3-phase (a,b,c) -> rotating dq frame */
void abc_to_dq(float ia, float ib, float ic, float theta_e, float *id, float *iq);

/* Inverse Park + Clarke: dq -> 3-phase (a,b,c) */
void dq_to_abc(float id, float iq, float theta_e, float *ia, float *ib, float *ic);

#endif
