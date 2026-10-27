# Sustained fault-window throughput decreases

Run `python3 analysis/throughput_drop.py` to regenerate `derived/throughput-drop/`, then `python3 analysis/plot_drop_summary.py` for the summary figure. Use `python3 analysis/throughput_drop.py --plots-only` to regenerate profile figures from the saved windows. Run `python3 analysis/validate_drop_outputs.py` for independent checks against the raw intervals. Run `python3 -m unittest discover -s analysis -p 'test_throughput_drop.py'` for interval-integration, gap, zero-rate, boundary and reference-support checks.

## Primary question

What is the largest observed 30-second sustained decrease in the sum of both clients' RBD read rates between confirmed OSD-down and data-repair completion, compared with an estimated progress-matched no-fault reference for the same configuration?

For a window W, integrate each client's reported interval read rate over its actual overlap with W, divide by W's duration, and sum both client rates. The rate in a CSV row belongs to the interval from the previous row timestamp through the current timestamp, not the following interval. The decrease is `100 * (1 - fault_aggregate / reference_aggregate)`; absolute decrease is `reference_aggregate - fault_aggregate` in MiB/s.

The two clients share the same fault-window start/end timestamps. Their reference estimates are conditioned separately on their current pass and progress, then summed within each no-fault trial. Finally, average the three no-fault trial estimates. This synthetic expected aggregate avoids forcing unsynchronized clients into one common baseline timestamp, but is not an observed contemporaneous no-fault window.

## Progress cannot be aligned to exact simulation-step timestamps

The recorded application CSVs contain exact global byte totals, per-step phase durations, and cumulative phase time. They do not contain per-step wall-clock timestamps. Summing maximum-rank read/compute/write times does not reliably reconstruct wall time; maxima can occur on different ranks. The analysis therefore does not invent exact step timestamps.

Use cumulative measured RBD reads, normalized within each recorded pass, as a progress proxy. Application CSVs verify 3,600 steps and 900 GiB of logical input per pass. Reference windows of the same duration and pass are matched within ±0.01 normalized progress (one percentage point). Calculate the median matched reference rate for each no-fault trial/client, sum the two client medians, then equally average the three trial estimates. All three reference trials and both clients must have matching support.

A pass must have at least 99% valid counter coverage and measured RBD reads between 0.9 and 1.1 times the logical payload; otherwise its progress estimate is rejected. These are diagnostic acceptance bounds, not evidence that progress is exact. All measured ratios and coverage fractions are published in progress-proxy-audit.csv. Readahead, filesystem metadata and caching still limit the approximation.

## Fixed window rules

- Window lengths 10, 30 and 60 seconds; three-second start grid anchored at each searched interval's start. The primary result uses 30 seconds.
- Trim six seconds from each recorded pass start and end. A valid window must remain inside a single pass on each client; clients may be on different pass numbers, with each matched separately to its own reference pass.
- Reject incomplete counter coverage and intervals longer than six seconds. Missing counters are not zero; a genuine measured zero fault rate remains eligible.
- Do not filter observations because their rate looks too low or their decrease looks too large.
- Keep recovery-phase-crossing windows for the primary search, and label the overlap. Do not silently assign a mixed window to one phase.
- Search grace, remapping and active repair separately as secondary outputs. A subphase shorter than the window has no whole-phase maximum, not a measured zero decrease.
- Search the post-repair interval through the earlier client analysis end separately; the OSD is still down/out then under the experiment protocol. Do not mix this interval with active repair.
- OSD restoration occurs after the workload and is outside the primary metric.

OptLRC fault source trial 02 remains excluded; use 01/03/04. Replication uses its original primary-only campaign, not the balanced-read diagnostics.

## Interpretation

Report all three per-trial maxima, their mean and sample standard deviation, and the worst observed value. Percentage and absolute-decrease maxima may be different windows. Trial maxima depend on window length and searching over many overlapping windows; they are not independent samples or inferential confidence limits. The reference-trial min/max fields describe variation in the estimated reference, not a confidence interval.

These are decreases relative to an estimated no-fault reference, not a causal estimate attributable exclusively to the injected fault. Natural caches, scrubbing, placement and topology differences remain relevant. They also differ from whole-job logical throughput: RBD bandwidth includes filesystem traffic, while the application metric measures payload divided by total workload duration. Normal pass transitions remain visible in the plots and included in whole-job statistics, but cannot supply the reported active-window maximum.

## Absolute throughput presentation

`python3 analysis/throughput_context.py` regenerates a combined context CSV, all-trial worst-window rate CSV, two clearly separated tables, and a two-panel figure. Whole-job logical throughput is per client and averaged over three trial means; worst-window RBD throughput is aggregate across both clients at one selected window. Select the same maximum-percentage window for reference, fault rate, absolute decrease and percentage decrease. Do not substitute the separate maximum-absolute-decrease window. Full analysis also regenerates this context automatically.

## Per-client decomposition

`analysis/throughput_context.py` also regenerates `worst-aggregate-window-by-client.csv` and `worst-window-per-client.png`/`.svg`. Both clients are evaluated at each trial’s selected aggregate peak; per-profile report rows select the worst of those aggregate peaks. Per-client references are the mean of the same three trial medians used by the aggregate reference. Rates sum exactly; percentages are reference-rate-weighted, not additive. These values do not identify independent per-client maximum windows. Standalone regeneration: `python3 analysis/client_window_breakdown.py`.
