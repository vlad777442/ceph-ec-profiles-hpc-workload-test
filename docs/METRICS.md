# Metric dictionary

All reported throughput uses MiB/s (2²⁰ bytes/second), even when legacy CSV column names say MB.

| Field/file | Meaning |
|---|---|
| results.json: logical_input_bytes | Global bytes processed by that client's whole MPI job across its passes: 2,700 GiB for three passes. |
| logical_throughput_mib_s | Logical input bytes / whole analysis duration, including compute, writes, pass validation/relaunch gaps. Not read-phase-only bandwidth. |
| duration_analysis_s | Client workload interval from analysis start through validated completion. |
| trial.json: mean_client_mib_s | Arithmetic mean of the two client job throughputs; primary trial-level summary. |
| aggregate_mib_s | Total 5,400 GiB divided by earliest client start to latest client end. Can differ from the sum of independently timed client averages. |
| performance.csv.gz: timestamp | UTC Unix epoch seconds. elapsed_s starts with monitoring and may include the scheduled-start wait. |
| io_read_mb / io_write_mb | Interval bandwidth from the verified mapped RBD block-device counters. Includes RBD/filesystem I/O, unlike logical application payload. |
| read_iops / write_iops | Completed block requests per second for the mapped RBD device. |
| read_latency_ms / write_latency_ms | Interval block-accounting time divided by completed requests; not an end-to-end application latency distribution. |
| cpu_percent / memory_mb | Host-wide CPU percentage and used memory in MiB; not application-only utilization. |
| analysis_cpu_percent / analysis_rss_mib | Process-tree CPU percentage (may exceed 100%) and RSS for the analysis process tree. |
| net_rx_mb / net_tx_mb | Interval interface traffic; includes protocol/recovery/other traffic, not only application payload. |
| rbd_usage_mb | Used capacity of the mounted RBD filesystem, in MiB; not raw cluster disk usage. |
| pass-XX-throughput.csv.gz | Per-step application counters: exact global read/write bytes and maximum-rank phase times. Each full pass has 3,600 records and 900 GiB global input. |
| max_rank_*_time_sec | Maximum phase duration across ranks for the step. Different maxima may come from different ranks; summing them is not guaranteed to equal wall time. |
| global_read_phase_mib_s | Global step input bytes divided by maximum-rank read-phase duration. Distinct from whole-job logical throughput and from RBD bandwidth. |
| recovery.json / t_healthy | Observed completion of data repair while the failed OSD is down/out and all PGs are clean. This event does not mean the OSD is restored. |
| repair_min | t_healthy minus t_recovering; excludes the down/out grace period and later restoration. |
| down_to_clean_min | t_healthy minus t_down, including grace. |
| restoration.json | Separate convergence after restarting and marking the OSD in. |
| osd-perf.jsonl.gz | Ceph OSD commit/apply latency observations; these are not per-disk read-utilization metrics. |
| telemetry/ | Continuous raw /proc/diskstats, CPU and network counters on OSD hosts; align by epoch with each trial interval. Disk read/write sector counters use 512-byte sectors. |

First interval rates can be blank. Treat missing counters as missing observations, not measured zero. Figures skip invalid/blank rate rows, mark pass boundaries in gray, and mark analysis completion in purple. They display RBD traffic rather than logical payload throughput. Whole-workload slowdown does not measure the maximum dip during repair; recovery-window analysis must handle pass boundaries and restart gaps explicitly.
