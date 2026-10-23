# Sustained two-client osd.3 fault trial

Status: COMPLETE.

Repeated full passes over the same 900 GiB input; 8 MPI ranks per client; natural caches. Each client completes exactly three full passes. Repair completion is recorded even if it occurs after the workload ends. Pass boundaries and brief validation/relaunch gaps are recorded. OSD restoration occurs after the workload ends.

- node12: 3 passes, 172.0 minutes, 22.2 minutes after repair completed.
- node13: 3 passes, 172.0 minutes, 22.2 minutes after repair completed.

See summary.json, recovery.json, restoration.json and artifacts/ for raw metrics, pass logs, validated outputs and figures. An equivalent repeated-pass no-fault control is needed for paper comparisons.
