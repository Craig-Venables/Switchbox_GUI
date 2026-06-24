/* Shared segment-budget helpers for instrument-side PMU burst batching.
 * Include from USRLIB modules only (pmu_endurance_burst_test.c, etc.). */

#ifndef PMU_BURST_COMMON_H
#define PMU_BURST_COMMON_H

/* Practical conservative ceiling for pmu_endurance_interleaved (~20 cycles at 1 us). */
#define PMU_ENDURANCE_CONSERVATIVE_SEG_PER_BURST 350

/* 4225-PMU hardware seg-arb limit per channel. Burst test uses this so cycles run as
 * one continuous waveform (e.g. 100 cycles = 1806 segments, no inter-burst idle). */
#define PMU_MAX_SEG_PER_BURST 2048

/* Endurance: Initial Read (~6 segs) + 17 segs per SET/RESET cycle. */
#define PMU_ENDURANCE_SEG_FIXED 6
#define PMU_ENDURANCE_SEG_PER_CYCLE 18

/* Max cycles in one internal burst (also capped by per-burst waveform builder). */
#define PMU_ENDURANCE_MAX_CYCLES_PER_BURST 100

static inline int pmu_endurance_seg_estimate(int cycles, int skip_initial_read)
{
  if (cycles < 1)
    return 0;
  if (skip_initial_read)
    return PMU_ENDURANCE_SEG_PER_CYCLE * cycles;
  return PMU_ENDURANCE_SEG_FIXED + PMU_ENDURANCE_SEG_PER_CYCLE * cycles;
}

static inline int pmu_max_endurance_cycles_per_burst(int skip_initial_read)
{
  int budget = PMU_MAX_SEG_PER_BURST;
  int fixed = skip_initial_read ? 0 : PMU_ENDURANCE_SEG_FIXED;
  int cap;

  if (PMU_ENDURANCE_SEG_PER_CYCLE < 1)
    return 1;

  cap = (budget - fixed) / PMU_ENDURANCE_SEG_PER_CYCLE;
  if (cap < 1)
    cap = 1;
  if (cap > PMU_ENDURANCE_MAX_CYCLES_PER_BURST)
    cap = PMU_ENDURANCE_MAX_CYCLES_PER_BURST;
  return cap;
}

static inline int pmu_endurance_probes_this_burst(int cycles, int skip_initial_read)
{
  if (cycles < 1)
    return 0;
  if (skip_initial_read)
    return 2 * cycles;
  return 1 + 2 * cycles;
}

#endif /* PMU_BURST_COMMON_H */
