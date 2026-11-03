# Additional OptLRC trials: memory-reserve-512m

Separate cohort: the client memory reserve changed from 90112 to 524288 KiB after an RBD copy-up allocation/write failure. Original comparison figures and drop references continue to use the original three trials per condition. These are two additional independent trials per condition, not five trials in an unchanged environment.

| Condition | Trial | Mean client MiB/s | Mean duration (min) | Repair (min) |
|---|---:|---:|---:|---:|
| no-fault | 5 | 316.02 | 145.82 | — |
| no-fault | 6 | 317.77 | 145.01 | — |
| fault-osd3 | 5 | 296.82 | 155.24 | 47.49 |
| fault-osd3 | 6 | 296.19 | 155.58 | 44.82 |

Both clients completed and validated all three passes in each trial. No new kernel allocation/write errors were observed during the repaired campaign. Complete input checksums matched before and after. The two clients within a trial are dependent observations. The failed extension no-fault04 is excluded, with diagnosis in provenance/campaigns/optlrc/memory-reserve-512m/. Source code, original settings, policy change, original/packaged file hashes and compressed telemetry are preserved.
