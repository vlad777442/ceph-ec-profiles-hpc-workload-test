# Initial actual-workload read-mode comparison

Both two-client runs completed three validated passes per client. Primary-only: mean 202.456 MiB/s/client; replica-balanced: mean 262.325 MiB/s/client (+29.57%). The original baseline near 202.6 MiB/s reproduces. The mode difference is material but order/cache effects remain possible, so the approved plan calls for reverse-order confirmation.

Per-client performance/application CSVs and cluster snapshots exist. The OSD disk collector failed immediately because SSH to node0 lacked a verified host key, causing the migration wrapper to fail after both workloads completed. Per-OSD disk utilization is therefore unavailable for this first pair; do not label its telemetry complete. Fixed collector reads node0 counters locally and retains SSH verification on other nodes. Original failed logs are preserved. Clay and scratch images remain untouched; no faults or deletions.
