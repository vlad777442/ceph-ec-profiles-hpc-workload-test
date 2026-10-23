# Sustained two-client osd.3 fault trial

Status: COMPLETE.

Repeated full passes over the same 900 GiB input; 8 MPI ranks per client; natural caches. The controller requested a stop 15 minutes after data repair completed; each client then finished its current full pass. Pass boundaries and brief validation/relaunch gaps are recorded. OSD restoration occurs after the workload ends.

- node12: 3 passes, 153.4 minutes, 53.7 minutes after repair completed.
- node13: 3 passes, 153.4 minutes, 53.7 minutes after repair completed.

See summary.json, recovery.json, restoration.json and artifacts/ for raw metrics, pass logs, validated outputs and figures. An equivalent repeated-pass no-fault control is needed for paper comparisons.
