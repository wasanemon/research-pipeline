# Verification pass log — 2026-07-06 (pass 1)

Started from HANDOFF §3(A): adversarial verification of the 11 notes that were marked as written but not yet independently source-checked.

## Working constraints

- Local `git clone` from the sandbox failed because GitHub DNS resolution was unavailable in this environment.
- To keep work moving, this pass used the repository contents via GitHub API and source materials via public web/open-access PDFs.
- This file records the start of the verification pass and what was checked so far.

## Method for this pass

For each target note in this initial pass:
1. open the current note from `literature/notes/`
2. resolve the corresponding public source page or PDF
3. spot-check title / venue / year / source URL consistency
4. spot-check headline claims, numbers, and anchors that are prominent in the note
5. record whether a factual correction is immediately required

This is **not yet the full completion of §3(A)**. It is the first committed verification-pass artifact.

## Checked in this pass

### 1) `2026-fast-pan-unicom.md`
- Source used: `https://www.usenix.org/system/files/fast26-pan.pdf`
- Confirmed from source:
  - published title matches the note
  - venue is FAST '26 / USENIX FAST 2026
  - core mechanism names TagSched / TagPoll / SKIP match the paper
  - the note's highlighted figures are consistent with the paper excerpts checked in this pass, including:
    - ext4 throughput at low thread counts averaging 62.9% of BypassD
    - BypassD mixed-workload C-thread performance dropping to 39.1% of ext4 at 32 threads
    - syscall mode-switch latency of about 150 ns
    - dedicated completion-thread ceiling around 1820 KIOPS
- Result in this pass: no immediate factual correction identified from the checked claims

### 2) `2026-edbt-chen-thunderbolt.md`
- Source used: `https://www.openproceedings.org/2026/conf/edbt/paper-29.pdf`
- Confirmed from source:
  - published title matches the note
  - DOI `10.48786/edbt.2026.07` and EDBT '26 venue labeling match
  - the paper explicitly states the 50× headline improvement claim
  - reconfiguration result checked: `K' = 10` corresponds to about `80K TPS`, and `K' > 1000` to about `180K TPS`
  - cross-shard result checked: at 100% cross-shard load, Thunderbolt still reports about `19K TPS`
- Result in this pass: no immediate factual correction identified from the checked claims

### 3) `2026-vldbj-simatis-temporal-indexing.md`
- Sources used:
  - `https://link.springer.com/article/10.1007/s00778-026-00968-6`
  - open-access PDF mirror discovered during verification
- Confirmed from source:
  - the published title is indeed `Scalable lighting-fast temporal indexing`
  - publication metadata matches the note: The VLDB Journal, volume 35, article 17, published 2026
  - the LIT+ description in the note is aligned with the paper's explanation of memory-budget-bounded in-memory handling and disk-resident fossils / FossilIndex
- Result in this pass: no immediate factual correction identified from the checked claims
- Important clarification: the note's question about `lighting-fast` vs `lightning-fast` remains worth remembering, but the published journal title itself uses `lighting-fast`

## Remaining §3(A) targets

Still to be adversarially checked:
- `2026-edbt-gao-recdb.md`
- `2026-edbt-shen-dcsr.md`
- `2026-fast-park-lockify.md`
- `2026-fast-song-warp.md`
- `2026-fast-tu-most.md`
- `2026-fast-an-xerxes.md`
- `2026-fast-yoon-cylon.md`
- `2026-fast-kim-zoned-ufs.md`

## Notes for the next pass

- Continue using open-access publisher PDFs where possible (USENIX / OpenProceedings / Springer OA were accessible in this pass).
- The next best targets are the remaining FAST and EDBT notes because their source PDFs are likely similarly reachable.
- If a factual mismatch is found in later passes, update the note itself and append a specific Changelog entry describing the correction.
