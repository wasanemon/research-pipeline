---
name: literature-notes
description: >
  Write and maintain structured literature notes (one Markdown file per paper) for
  database systems research, with strict source-grounding and claim-labeling rules.
  Use this skill whenever the user asks to summarize a paper, take reading notes,
  process the literature queue, compare papers, or extract limitations / open
  problems from prior work — even if they just say "read this PDF" or "この論文
  まとめて". Also consult it before answering questions from existing notes.
---

# Literature Notes Protocol

## Golden rules

1. **A note may only contain what was verified in an actual source** (the PDF, the
   arXiv abstract page, or an API response). No memory-based content, ever.
2. Every technical claim carries an **anchor**: `(§4.2)`, `(Table 3)`, `(p.7)`,
   or `(abstract)`. A claim you cannot anchor does not go in the note.
3. Distinguish voice with labels: `[paper]` = the paper's own claim;
   `[inference]` = your reasoning; `[question]` = an open doubt to verify later.
4. If only the abstract was read, set `status: abstract-only` in the frontmatter and
   write **no** algorithmic details or experimental numbers beyond the abstract.
5. Notes are append/revise, not overwrite. Log substantive changes under `## Changelog`.

## File naming

`literature/notes/<year>-<venue>-<firstauthor>-<slug>.md`
e.g. `2020-vldb-lu-aria.md`, `2024-arxiv-smith-mvcc-numa.md`.
Venue is the DBLP venue abbreviation lowercased; use `arxiv` for preprints.

## Note template

Copy `assets/note-template.md`. Structure:

```markdown
---
title: ""
authors: []
venue: ""            # PVLDB / SIGMOD / arXiv ...
year:
ids: {doi: "", arxiv: "", dblp: ""}
urls: {paper: "", pdf: "", code: ""}
status: abstract-only | skimmed | read | deep-read
read_date: YYYY-MM-DD
tags: []             # e.g. [occ, deterministic, larger-than-memory]
---

## TL;DR
2–3 sentences, in your own words. What problem, what idea, what result.

## Problem & motivation
What gap does the paper claim to fill? `[paper]` claims only, anchored.

## System model & assumptions
Workload assumptions, hardware assumptions, consistency level targeted,
failure model. This section is where hidden assumptions get flushed out —
be exhaustive, they are the raw material for idea generation.

## Approach
The core technique. Enough detail that a reader could compare it against
another protocol without reopening the PDF. Anchored throughout.

## Evaluation
- Setup: hardware, benchmarks (YCSB/TPC-C/...), baselines, key parameters. (anchor)
- Headline numbers, each anchored: "4.2× over Silo at 64 threads under
  high contention (Fig. 7)".
- `[inference]` What the evaluation does NOT cover (missing baselines,
  missing workloads, unrealistic parameter choices).

## Limitations
- Stated by authors `[paper]` (anchor)
- Inferred `[inference]` — be specific and falsifiable.

## Relations
- Builds on / competes with / contradicts: link other notes by filename.

## Idea seeds
`[inference]` or `[question]` items only. Each one: a sentence + why it might
matter + what a first validation experiment would look like. These feed ideas/
in Phase 2 — write them even if half-baked, but never dress them up as findings.

## Changelog
- YYYY-MM-DD: created (status: read)
```

## Working the queue

1. Pick entries from `literature/queue.md`, priority: `core` > `adjacent` >
   `borderline`; within a band, newest first unless the human reordered.
2. Download the PDF into `literature/pdfs/` (record the URL used). If no PDF is
   accessible, write an abstract-only note — do not simulate having read it.
3. Write the note, flip the queue checkbox to `- [x]`, commit with message
   `note: <filename>`.
4. When a note reveals an important cited work not yet in the queue, add it via the
   paper-collection skill (Mode B) — do not write a note for it from memory.

## Answering questions from notes

When the human asks a question across the note corpus ("which papers assume
uniform keys?"), answer only from note contents and cite note filenames. If notes
are insufficient, say so and offer to deep-read the relevant PDFs — do not fill
gaps from memory.
