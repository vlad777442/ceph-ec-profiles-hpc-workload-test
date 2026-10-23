# Provenance and packaging

Original research measurements were collected under `/users/vlad777/research/erasure-coding` and retained client directories in ADIOS2-Examples/results. This bundle preserves source profile/condition/trial IDs. `provenance/file-sources.json` records each collected file's source SHA-256 and packaged SHA-256. No private key or keyring content is intentionally collected. Credential-named JSON fields are redacted if present; generic paths to credential files are not credentials.

CSV and JSONL logs, plus text analysis logs, are losslessly compressed with deterministic gzip headers. JSON is serialized for portability and redaction. Plain CSV files use LF line endings for stable Git checkout checksums. Historical raw measurement values remain unchanged. Generated figures and normalized trial metadata are derived artifacts. `SHA256SUMS` covers all repository content except Git internals and the checksum file itself.

Workload source repository: https://github.com/vlad777442/ADIOS2-Examples . Commit 55f54beb02f87210bb4c541421932473cac94d99 published the experiment-runner improvements. Campaign runner files subsequently changed locally; exact snapshots/hashes in the measurements and `provenance/runners/` are more precise than assuming the Git commit alone identifies every runner.

The recorded analysis binary SHA-256 is fb8b5bab8124d2a6a2bf887fdb64d7943997695be5a7efac84319e6b515214f6. The collected pdf-calc.cpp SHA-256 is 0808e91e8e8ccc248036c2e81dcb8f96903ba07d15f50f42d8431ac47f0f2e81 and matches the earlier published working source. Current client Git HEAD at collection was feee7a1db601056fc2fce008b175dfbbdf93a0a2 (later commits added results); this alone does not identify a rebuild. Captured workload source/XML/settings and the upstream license are in `provenance/workload/`.

Custom OptLRC library SHA-256: f9799e0bb8eed7cdbe5fd39b254d8b298a694a2e4af8d2f0e643bb5dc576d65f. Its ABI reports Reef 18.2.8. The supplied binary's exact source/build provenance is unconfirmed. Relevant source references are https://github.com/olekol33/optlrc2018 (local inspected commit be910c1bebbf78ad5be5552a8ffed12c229b4456) and https://github.com/Azen233/Optimal-LRCs_erasure_coding . Reference generator tables matched; this is not proof that either source checkout exactly produced the supplied binary. Binary redistribution is intentionally omitted.

Large input and BP5 outputs, compressed backup archives, daemon binaries, core dumps, live client credentials, keyrings, environment caches, and ceph-ansible source tarballs are excluded. Input manifests include the per-file checksums and sizes, not the dataset. Historical controllers contain original cluster paths and fault commands; the upload bundle's analysis/validation scripts do not execute them.

No new license is assigned to the research measurements or custom scripts by this packaging step. The captured ADIOS2-Examples source retains its supplied upstream license.
