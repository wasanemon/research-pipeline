# Verification pass log — 2026-07-06 (pass 2)

Continued from `logs/2026-07-06-verification-pass-1.md`.

This pass covered the **remaining 8 notes** listed in HANDOFF §3(A), using the repository notes plus publicly reachable publisher/open-access sources to perform source-grounded spot checks.

## Scope of this pass

For each note in this pass, I checked at least one of the following against a public source:
- title / venue / publication labeling
- key headline result numbers
- whether the note's main claimed mechanism matches the source

This pass is still a **verification-progress artifact**, not the final completion marker for §3(A).

## Notes checked in this pass

### 1) `2026-edbt-gao-recdb.md`
- Source used: `https://openproceedings.org/2026/conf/edbt/paper-229.pdf`
- Confirmed from source:
  - title matches the note
  - the paper explicitly claims `1.03×–2.94×` end-to-end training speedup over RocksDB
  - the note's access-skew claim is consistent with the source: more than `99%` of accesses are contributed by `1%` of embedding vectors
  - the note's read-amplification claim is consistent with the source: SSD `28` vs LSM-tree `124`
  - the note's compaction-interference claim is consistent with the source: read latency can increase by up to `258%`
- Result in this pass: no immediate factual correction identified from the checked claims

### 2) `2026-edbt-shen-dcsr.md`
- Source used: `https://openproceedings.org/2026/conf/edbt/paper-246.pdf`
- Confirmed from source:
  - title matches the note
  - the paper states support for around **ten million updates per second**
  - the abstract-level average speedups in the note match the source:
    - `5.84×` over PPCSR
    - `12.98×` over CPMA
    - `25.63×` over PaC-tree
    - `27.45×` over Terrace
    - `11.14×` over LSGraph
  - the source also confirms the note's statement that the additional sorting phase can account for over `80%` of update time for large batches
- Result in this pass: no immediate factual correction identified from the checked claims
- Follow-up worth deeper checking later: the note's own `[question]` about the Figure 11 batch-size wording remains worth revisiting directly in the PDF if a fully adversarial line-by-line pass is done

### 3) `2026-fast-park-lockify.md`
- Source used: `https://www.usenix.org/system/files/conf%C3%A9rence/fast26/fast26spring-prepub_park.pdf`
- Confirmed from source:
  - title matches the note
  - core mechanisms `self-owner notification` and `asynchronous ownership management` are explicit in the paper
  - the low-contention degradation claim is consistent with the source: throughput can drop by up to `86%`
  - the latency-breakdown claim is consistent with the source: DLM operations contribute `47%` in the 5-client case
  - the paper reports about `6.4×` throughput improvement
  - the RDMA comparison note is consistent with the source: Lockify reaches `87–88%` of the emulated DLM-over-RDMA throughput
- Result in this pass: no immediate factual correction identified from the checked claims

### 4) `2026-fast-song-warp.md`
- Source used: `https://www.usenix.org/system/files/fast26-song.pdf`
- Confirmed from source:
  - title matches the note
  - the worst-case WAF figures in the note align with the paper: SSD A `2.58×`, SSD B `4.49×`
  - `Noisy RUH` and `Save Sequential` are explicitly named and analyzed in the paper
  - the CacheLib optimization claim is consistent with the source: WAF improves from `2.00` / `1.37` / `1.16` across NoFDP / FDP / +Small RU Opt for the shown case
- Result in this pass: no immediate factual correction identified from the checked claims
- Follow-up worth deeper checking later: the note's internal `[question]` markers about some figure-number attribution nuances remain reasonable to keep until a figure-by-figure PDF check is completed

### 5) `2026-fast-tu-most.md`
- Sources used:
  - `https://www.usenix.org/conference/fast26/presentation/tu`
  - `https://www.usenix.org/system/files/fast26_slides_tu.pdf`
- Confirmed from source:
  - title matches the note
  - MOST / Cerberus framing is consistent with the note
  - the headline throughput/write-reduction direction is consistent with the talk materials, including `up to 2.3x higher throughput` and `reduces writes by up to 84%`
- Result in this pass: no immediate factual correction identified from the checked claims
- Follow-up worth deeper checking later: the precise paper-side source for every specific number in the note (for example the strongest P99 claim) should still be line-checked in the PDF during a stricter adversarial pass

### 6) `2026-fast-an-xerxes.md`
- Source used: `https://www.usenix.org/system/files/fast26-an.pdf`
- Confirmed from source:
  - title matches the note
  - the paper reports validation errors ranging from `0.1% to 10%`
  - the snoop-filter result in the note is consistent with the paper: compared to FIFO, LIFO improves bandwidth by `5%` and reduces average latency by `15%`
- Result in this pass: no immediate factual correction identified from the checked claims

### 7) `2026-fast-yoon-cylon.md`
- Source used: `https://www.usenix.org/system/files/fast26-yoon.pdf`
- Confirmed from source:
  - title matches the note
  - the architecture figure and evaluation are consistent with the note's core fast/slow path summary: `150ns` hit path and `40µs` miss-path fetch in the overview figure
  - the QEMU/Cylon latency-breakdown values in the note match the paper excerpts checked here:
    - `14.74µs` for QEMU-CXL
    - `16.27µs` for Cylon-S miss-path latency
    - `23.04µs` for Cylon-I miss-path latency
  - the latency-distribution summary is consistent with the source: Cylon average hit-side figure `977ns` and QEMU average around `14.6µs`
- Result in this pass: no immediate factual correction identified from the checked claims

### 8) `2026-fast-kim-zoned-ufs.md`
- Source used: `https://www.usenix.org/system/files/fast26-kim-jungae.pdf`
- Confirmed from source:
  - title matches the note
  - the proactive-GC knob values referenced in the note are present in the paper excerpts checked here, including:
    - `reserved_segments = 6336`
    - `gc_no_zoned_gc_percent = 60%`
    - `gc_boost_zoned_gc_percent = 25%`
  - the application-level result checked here is consistent with the note: game loading improves from `35s` to `30s` (`14%`)
  - the photo-scrolling metrics in the note are consistent with the source excerpt checked here:
    - average fragments/file `46.29` → `2.31`
    - average fragment length `99KB` → `1,979KB`
    - p99 frame time `16ms` → `11ms`
- Result in this pass: no immediate factual correction identified from the checked claims

## Overall status after pass 2

- All 11 notes from HANDOFF §3(A) have now at least been covered by a **source-grounded verification start / spot-check pass** across pass 1 and pass 2.
- In this pass, I did **not** find an immediate factual mismatch that clearly requires a note edit right away.
- However, several notes still contain their own `[question]` markers or figure-level ambiguities that should be revisited if the goal is a stricter, fully adversarial claim-by-claim completion criterion.

## Suggested next verification step inside the repo

If continuing immediately, the next highest-value move is:
1. reopen the notes that still contain explicit `[question]` markers or figure/caption ambiguities
2. verify those exact lines against the PDF figures/tables/captions
3. only if a mismatch is confirmed, edit the note and append a precise Changelog correction entry

## Notes checked across both passes

Pass 1:
- `2026-fast-pan-unicom.md`
- `2026-edbt-chen-thunderbolt.md`
- `2026-vldbj-simatis-temporal-indexing.md`

Pass 2:
- `2026-edbt-gao-recdb.md`
- `2026-edbt-shen-dcsr.md`
- `2026-fast-park-lockify.md`
- `2026-fast-song-warp.md`
- `2026-fast-tu-most.md`
- `2026-fast-an-xerxes.md`
- `2026-fast-yoon-cylon.md`
- `2026-fast-kim-zoned-ufs.md`
