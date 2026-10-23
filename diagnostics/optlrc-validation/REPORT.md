# OptLRC validation — decoder issue blocks rollout

Library SHA256: f9799e0bb8eed7cdbe5fd39b254d8b298a694a2e4af8d2f0e643bb5dc576d65f. Local ABI version 18.2.8 matches installed Reef. Node0 loads the library. Installed only the previously absent /usr/lib/ceph/erasure-code/libec_optlrc.so on node0 for standalone tests; no propagation, daemon restart, cluster profile, pool or migration.

## Corrected candidate profile

plugin=optlrc n=10 k=6 r=4 mapping=DDDD_DD___ ruleset-failure-domain=osd crush-failure-domain=osd stripe_unit=12288

Upstream generator matrix has systematic data rows 0,1,2,3,5,6, not 0–5. The original experimental mapping DDDDDD____ was wrong and its failed tests are retained only as investigation history. The corrected candidate reports 10 total / 6 data / 4 coding chunks. Legacy ruleset-* placement parameters require actual CRUSH validation before any future rollout.

Chunk-size calculation rounds to 192-byte alignment. Offline stripe_unit=4096 failed ECUtil chunk-size assertion; 12288 works, giving a 73728-byte full stripe. Production stripe behavior, RBD overwrites and generated CRUSH rule remain unvalidated. Do not deploy the candidate based only on these tests.

## Correct-mapping reconstruction results

Random payload: 73728 bytes. Full-shard decode matches. All 10 single-shard-loss cases match exactly. Of 45 two-shard-loss cases, only 28 match; 17 return success but incorrect bytes. Per-pattern outcomes and payload hashes are in offline-correct-mapping/summary.json and status.json. Test program and payloads are retained for reproduction.

The likely related upstream code explicitly assumes at most one erasure per local group in _minimum_to_decode and uses XOR local repair. This source is a reference, not proof of the exact binary provenance. Review correct error propagation and global decode/fallback behavior against the actual build source before migration. Passing single-OSD tests does not validate multi-failure correctness or data safety under future degraded states.

Reference: https://github.com/Azen233/Optimal-LRCs_erasure_coding/blob/main/src/erasure-code/optlrc/ErasureCodeOptLrc.cc
Generator: https://github.com/Azen233/Optimal-LRCs_erasure_coding/blob/main/src/erasure-code/optlrc/ErasureCodeOptLrc_configs.h

Standalone ceph-erasure-code-tool has additional invalid-profile error-path crashes; these were local utility processes, not MON/OSD crashes. Their logs are preserved. No live-cluster fault injection occurred. Next step is validate/fix the actual decoder implementation and rerun offline tests before distributing the plugin or creating an OptLRC pool.

## Local original repository clarification

Inspected /users/vlad777/optlrc2018 at commit be910c1bebbf78ad5be5552a8ffed12c229b4456 (origin olekol33/optlrc2018). README.txt explicitly limits this implementation to one erasure per local group, unlike the full theoretical code. The generator tables are byte-for-byte identical to the reference tables. Tested corrected mapping DDDD_DD___ has groups 0–4 and 5–9. All 25 two-loss patterns with one erasure in each group pass. Of 20 same-group pairs, 3 parity-only pairs need no missing data reconstruction and pass; the other 17 return incorrect bytes with success. Thus the failures are outside the documented local-only decoder support; they do not show a failure of single-erasure local reconstruction. Returning success on unsupported reconstruction remains a real correctness/error-handling issue.

The original decoder has the same local-XOR approach and an apparent missing validation of available local helpers in decode_chunks; _minimum_to_decode rejects some same-group failures but the direct decode path can still report success. The original source predates Reef; do not substitute/build it unmodified into the running Reef cluster. The exact supplied library provenance is still unconfirmed. A single-OSD-only research variant could be considered after live scratch validation and explicit restrictions, with proposed min_size=9 so fewer than nine available shards block I/O. This would be a different configuration from prior min_size=7 EC runs and must be disclosed. No additional cluster changes made.
