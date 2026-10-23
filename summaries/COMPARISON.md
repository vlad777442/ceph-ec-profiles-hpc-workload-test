# Selected-trial comparison

Means are calculated from three two-client trial means per condition. Throughput is whole-workload logical MiB/s per client. SD is the sample standard deviation of trial means.

| Configuration | No fault ± SD | Fault ± SD | Whole-job drop | Repair (min) |
|---|---:|---:|---:|---:|
| reed-solomon | 329.3 ± 1.8 | 301.5 ± 1.0 | 8.5% | 79.9 |
| replicated-3 | 202.6 ± 2.5 | 199.7 ± 3.5 | 1.4% | 48.8 |
| lrc | 311.5 ± 1.3 | 289.3 ± 2.0 | 7.1% | 83.0 |
| clay | 301.4 ± 0.7 | 270.0 ± 2.1 | 10.4% | 114.1 |
| optlrc | 314.4 ± 0.3 | 294.2 ± 0.9 | 6.4% | 62.6 |

Repair excludes the automatic down/out grace period and subsequent OSD restoration. Whole-job drop is not a maximum recovery-window dip. OptLRC fault source trials are 01, 03 and 04; 02 is retained but excluded. Configuration/redundancy/stripe, PG topology, occupancy, cache and scrub differences limit causal comparisons; see docs/METHODOLOGY.md.
