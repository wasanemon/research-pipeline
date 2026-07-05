---
name: paper-collection
description: >
  Collect papers in database systems (DB / DBMS / concurrency control / storage /
  distributed transactions) from arXiv, DBLP, and Semantic Scholar, deduplicate them,
  and append them to literature/queue.md with machine-fetched metadata and BibTeX.
  Use this skill whenever the user asks to run the weekly collection, fetch new papers,
  add a specific paper to the pipeline, build a reading list, follow citations of a
  paper, or update references.bib — even if they just paste an arXiv link or a paper
  title and say "add this".
---

# Paper Collection Protocol

## Golden rules (repeated from CLAUDE.md because they matter)

- Metadata and BibTeX come **only** from API responses, never from memory.
- Every queue entry must carry at least one source URL.
- Rate limits: arXiv ≥ 3 s between requests; Semantic Scholar ≤ 1 req/s; DBLP be polite (≥ 1 s).
- Failed fetches are recorded as `FETCH-FAILED`, never silently dropped.

## Data sources and endpoints

| Source | Use for | Endpoint |
|---|---|---|
| arXiv API | New preprints, abstracts, PDF links | `http://export.arxiv.org/api/query?search_query=...` (Atom XML) |
| DBLP | Authoritative venue lists, **BibTeX** | `https://dblp.org/search/publ/api?q=...&format=json`; BibTeX: `https://dblp.org/rec/<key>.bib` |
| Semantic Scholar | Citations/references graph, abstracts, open-access PDF links | `https://api.semanticscholar.org/graph/v1/paper/...` |

`scripts/fetch_paper.py` wraps all three. Prefer it over ad-hoc curl so that output
format stays consistent. Read `python scripts/fetch_paper.py --help` before first use.

## Modes of operation

### Mode A — Weekly sweep (default when user says "collect" / "weekly run")

1. Query arXiv for the last 7–10 days in categories listed in CLAUDE.md
   (`cat:cs.DB`, plus `cs.DC` / `cs.OS` filtered by the keyword list).
2. Query DBLP for new entries in the monitored venues (DBLP updates when proceedings
   are published; check venues that had recent deadlines/publication dates).
3. For each hit, apply the **relevance filter** (below), then **dedup** (below),
   then append survivors to `literature/queue.md`.
4. Fetch BibTeX from DBLP for every accepted entry into `literature/references.bib`
   (arXiv-only papers: generate from arXiv metadata, tagged `note = {arXiv preprint}`).
5. Report: N found / N accepted / N duplicates / N failed, plus 3–5 highlights with
   one-line reasons. Do not decide research direction — that is the human's gate.

### Mode B — Single paper intake (user pastes a link/title/DOI)

1. Resolve the identifier via `fetch_paper.py`. If given only a title, search DBLP
   first (authoritative), then arXiv; if both return multiple candidates, show the
   candidates and ask which one — do not guess.
2. Dedup → append to queue → fetch BibTeX.

### Mode C — Citation expansion (user says "follow the citations of X")

1. Use Semantic Scholar `/paper/{id}/references` and `/citations`
   (fields: `title,year,venue,externalIds,abstract,citationCount`).
2. Apply relevance filter; cap at ~20 accepted entries per expansion unless told
   otherwise; sort by citationCount within the same recency band.
3. Mark queue entries with `via: citation-of <paper-key>` so provenance is visible.

## Relevance filter

Accept a paper if its title/abstract matches the CLAUDE.md keyword list **or** it is
from a monitored venue and concerns transaction processing, storage engines, indexing,
recovery, or memory/disk hierarchy. When unsure, accept but tag `relevance: borderline`
— the human prunes the queue; you do not silently discard borderline items.

Reject without queueing: pure ML papers using "transaction" in a financial sense,
blockchain-only papers unless they contribute a general CC/consensus technique,
and demos/posters under 4 pages (tag exceptions if seminal).

## Deduplication

A paper's identity key is, in priority order: DOI → arXiv ID → DBLP key →
normalized title (lowercase, alphanumerics only). Before appending, grep
`literature/queue.md` and `literature/notes/` for the identity key. If a preprint
already in the queue later appears at a venue, **update** the existing entry
(add DOI/venue, replace BibTeX with the DBLP version) rather than adding a new one.

## queue.md entry format

Append entries under the current month heading (`## 2026-07`), newest first:

```markdown
- [ ] **<Title>** — <First author> et al., <venue or arXiv>, <year>
  - id: <doi|arxiv|dblp key>  | added: <YYYY-MM-DD> | via: <weekly-sweep|manual|citation-of X>
  - url: <primary source URL>  | pdf: <pdf url or literature/pdfs/<file> or "none">
  - relevance: <core|adjacent|borderline> — <one-line reason>
```

`- [ ]` flips to `- [x]` only when a note exists in `literature/notes/`.

## Failure handling

Wrap network calls with retry (3 attempts, exponential backoff starting at 2 s).
On final failure, append the entry with `FETCH-FAILED (<step>, <error>)` instead of
metadata, so the human can see what's missing. Never fill gaps from memory.
