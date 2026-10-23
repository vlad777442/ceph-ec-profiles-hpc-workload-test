# Methodology, selection, and limits

## Workload and fault protocol

The Gray–Scott PDF analysis reads the same 900 GiB field payload on each client for each pass; 3,600 output steps and exact global input-byte totals are validated. Eight ranks run per client with core binding and 100 bins. Separate RBD images avoid mounting one ordinary ext4 filesystem read/write on two clients. The second image is cloned from a protected input snapshot, so the input is shared while outputs are separate.

Fault experiments stop osd.3 on node4 after approximately 280 seconds of analysis and let the MON mark it out automatically after approximately 600 seconds. The controller observes data repair, finishes the workload, then starts the OSD, marks it in, and waits for restoration. Polling introduces timing uncertainty of approximately the polling interval; see each record.

Original RS fault trials used an adaptive policy: continue at least 15 minutes after repair, then finish the current pass. All three selected RS fault trials completed three passes. Later campaigns fixed the workload at exactly three passes. This is a protocol difference even though the observed work matches; do not describe all stopping policies as identical. If repair extended beyond analysis, the controllers would retain that outcome rather than silently extending only that profile.

## Selection

Main campaigns select three trials per condition/profile. OptLRC fault trial 02 overlaps documented archival maintenance on the workload network during pass 3; preserve its data, exclude it from the primary comparison, and use replacement trial 04. This is an operational exclusion, not a selection based on whether throughput matches an expectation. The source trial IDs are unchanged.

For primary statistics, average the two clients within a trial, then average the three trial values. Report the trial-level sample standard deviation; two clients in one trial are dependent observations. Three trials provide limited uncertainty estimation. `summaries/trials.csv` retains both selected and excluded trial rows.

## Configuration differences

- Data failure domain is intentionally OSD, not host. A physical host failure can remove two OSDs; the campaigns inject one OSD failure only.
- RS(6,4), LRC(6,2,4), Clay(6,3,8), OptLRC(10,6,4), and replication 3 differ in redundancy and sometimes decoder capability. Equal field payload or shard count does not make protection equivalent.
- Clay uses EC stripe_unit 110592 and stripe_width 663552 to obtain 4KiB subchunks. Its nine shards, alignment, and extra preserved empty default-layout pool differ from prior configurations.
- OptLRC uses mapping DDDD_DD___, n=10, k=6, r=4, explicit m=4 for Reef accounting, stripe_unit 12288, stripe_width 73728, and min_size=9. The custom decoder implements local repair only. Correct-mapping offline tests passed all 10 single-shard losses and all 25 pairs spanning distinct local groups. Same-group pairs can return success with incorrect bytes. These experiments do not establish the theoretical code's full multi-failure tolerance. Live single-OSD writes/readback and final input hashes passed.
- Custom plugin installation initially exposed a Reef autoscaler capacity-accounting issue when m was absent. Explicit m=4 corrected accounting, the manager was restarted, and the reviewed crash record is retained. No paper trial ran with that unresolved error.
- Empty historical pools are retained, so total PG topology increases across campaigns: recorded original RS baselines have 256 PGs, replication 384, LRC 512, Clay 704, and OptLRC 832. See each baseline snapshot for actual values. Fixed 64-PG data pools do not imply equal total cluster topology.
- As older populated images were removed to isolate recovery, occupancy and object placement changed. Failed-OSD data volume and load also affect repair duration; repair-time ranking alone is not equal-work repair efficiency.
- The sole MANY_OBJECTS_PER_PG warning resulting from populated experiment pools plus empty historical pools was accepted and recorded in later campaigns. Other health failures remained blocking. No warning threshold was changed to hide it.
- Natural caches, sequential condition order, and scrub/deep-scrub activity remain possible confounders. Maintenance observations are retained. Fixed dataset bytes and matching binaries do not remove these effects.

## Replication diagnostics

Keep the original primary-only replication campaign as the baseline paired with its fault measurements. Actual-workload read-policy validation ran primary/balanced/balanced/primary, with three full passes per client in each trial. It showed a persistent balanced-read benefit, but it used different cluster occupancy and has no matched balanced-read fault campaign. First-pair per-OSD telemetry failed at startup; client/application and cluster metrics remain available. The repaired reverse-order collector recorded all 12 OSD hosts. Do not describe first-pair per-OSD telemetry as complete.

The separate small RBD probe used 32 GiB images and eight independent direct-read processes/client. It is not the MPI application and its smaller, warmer working set prevents substituting its numbers for the full workload.

## Data quality and presentation

Some historical LRC fault display labels incorrectly said replicated; the recorded pool/profile and campaign manifest identify LRC. Preserve original JSON labels for provenance; regenerated figures use canonical configuration labels. No measured rates or timestamps were rewritten for presentation.

Broken local symlinks for LRC fault trial 01 were repaired from the retained client result directories during collection. The upload bundle contains regular files, not environment-dependent symlinks.

Older May–September runs are retained in the original research workspace and omitted from this focused upload bundle: their CSV byte counts are per rank, dataset size is approximately 275 GiB, and hardware/profile provenance is incomplete. Some have invalid recovery chronology, unconfirmed fault state, or missing throughput CSVs. They are excluded from the current five-configuration summaries.
