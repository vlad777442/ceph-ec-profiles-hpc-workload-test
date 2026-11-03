# OptLRC repaired extension campaign

Four authorized additional trials: no-fault05, fault05, no-fault06, fault06. Failed no-fault04 remains preserved and excluded. Root cause: node13 kernel order-5 GFP_NOIO allocation failures in rbd_obj_copyup_read_parent, copy-up ENOMEM (-12), failed RBD writes and ext4 buffer errors. BP5 output became unreadable.

Temporary mitigation on both clients: vm.min_free_kbytes=524288 (was 90112); one-time memory compaction before diagnostics. No cache dropping, kernel replacement, flattening, pool changes or dataset deletion. Saved original settings permit restoration. This is a changed memory-policy cohort, not an identical repeat; retain cohort labels and report sensitivity against the original trials before pooling scientific results. Workload binary/XML/MPI and OptLRC profile remain unchanged.

Both clients must pass 8-GiB direct-write/read checksum and 3600-step/eight-rank BP5 output checks before this controller starts. Full input hashes run before and after the four trials. Live kernel log guards stop the controller on new allocation/copy-up/writeback errors, and fault controllers restore OSD3 even on abort. Original BP5 validation stays strict. The reserve is a mitigation, not a proven permanent kernel fix; full-duration repeat validation is required.

See state.json and campaign.log for progress. Diagnosis and memory-setting snapshots: ../five-trial-extension-20261101/diagnostics/.
