# Replication read-mode validation

Status: complete.

| Order | Read mode | Trial mean per client (MiB/s) |
|---|---|---:|
| primary then balanced | no | 202.5 |
| primary then balanced | balance | 262.3 |
| balanced then primary | balance | 256.3 |
| balanced then primary | no | 199.2 |

Across the two trial means per mode: primary-only 200.8 MiB/s/client; balanced 259.3 MiB/s/client (+29.1%). Trial is the unit of replication; the two clients are not independent trials.

Same input, binary, ADIOS2 XML, 8 ranks per client, 100 bins, and three 900GiB passes per client. The sequence is primary/balanced/balanced/primary with natural caches. Both modes use the existing 64-PG replicated data pool, size3/min2 and OSD failure domain; no global CRUSH, scrub, cache or read-policy settings changed. Only the verified replicated image mappings were remapped with explicit kernel read_from_replica=no or balance. Clay and scratch images remained populated; no faults or deletion occurred.

The first pair reproduced the original primary-only baseline (~202.5 MiB/s/client) and measured ~262.3 MiB/s/client with balanced reads. This is evidence about the chosen read configuration. Reverse-order repetition checks persistence but cannot fully eliminate cache, maintenance, or time effects. It does not establish that replication and EC algorithms alone explain their performance gap.

Historical EC no-fault means: RS 329.3, LRC 311.5, Clay 301.5 MiB/s/client. These used different PG topology/occupancy; Clay additionally used different stripe alignment and redundancy. Treat these as contextual observations rather than a matched causal comparison.

First-pair per-OSD disk telemetry is missing because its collector failed at startup; client performance/application CSVs and cluster status exist. Reverse-order disk counters are in osd-host-telemetry-reverse/. Do not describe first-pair per-OSD monitoring as complete.
