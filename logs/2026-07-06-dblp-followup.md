# DBLP follow-up — 2026-07-06

This note records which recent additions now have confirmed DBLP keys and which still need a later BibTeX refresh.

## Confirmed DBLP keys in this session

- `2021-sigmod-zhou-foundationdb.md`
  - confirmed DBLP key: `conf/sigmod/ZhouXSNMTABSLRD21`
- `2025-pacmmod-nguyen-autonomous-commit.md`
  - confirmed DBLP key: `journals/pacmmod/NguyenAZL25`
- `2026-arxiv-zhou-milliscale.md`
  - confirmed DBLP key: `journals/corr/abs-2603-02108`

## Still waiting / not yet refreshed

- `2026-pvldb-kuschewski-btrlog.md`
  - still appears not to have a DBLP record yet from the checks performed in this session
  - keep `ids.dblp` blank for now
  - later action: once DBLP record appears, replace the current arXiv-style BibTeX in `literature/references.bib` with the machine-obtained DBLP entry

## References file follow-up

I did not update `literature/references.bib` in this pass.
The immediate high-value next change there is:
1. add DBLP-derived entries for the three now-confirmed keys if they are not already present
2. later replace the BtrLog arXiv BibTeX once its DBLP record exists
