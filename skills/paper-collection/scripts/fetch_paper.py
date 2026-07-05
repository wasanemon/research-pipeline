#!/usr/bin/env python3
"""Unified paper metadata fetcher for the research pipeline.

Sources: arXiv API (Atom), DBLP (JSON search + BibTeX), Semantic Scholar Graph API.
Stdlib only — no external dependencies.

Usage:
  fetch_paper.py arxiv 2403.01234              # metadata for an arXiv ID
  fetch_paper.py arxiv-search "cat:cs.DB" --days 10 --max 50
  fetch_paper.py dblp-search "aria deterministic database" --max 10
  fetch_paper.py dblp-bib conf/vldb/LuHTY20    # BibTeX for a DBLP key
  fetch_paper.py s2 DOI:10.14778/3407790.3407808 --refs   # + references
  fetch_paper.py s2 arXiv:2403.01234 --cites               # + citations

Output: JSON to stdout (except dblp-bib, which prints raw BibTeX).
All network calls: 3 retries with exponential backoff; polite rate limiting.
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = "research-pipeline/0.1 (academic literature tooling)"
LAST_CALL = {}  # per-host politeness timer

MIN_INTERVAL = {  # seconds between requests, per host
    "export.arxiv.org": 3.0,
    "dblp.org": 1.0,
    "api.semanticscholar.org": 1.1,
}


def _get(url, timeout=30):
    host = urllib.parse.urlparse(url).netloc
    wait = MIN_INTERVAL.get(host, 1.0) - (time.time() - LAST_CALL.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                LAST_CALL[host] = time.time()
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"FETCH-FAILED after 3 attempts: {url} ({last_err})")


# ---------------------------------------------------------------- arXiv ----

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _parse_arxiv_entry(e):
    aid = e.findtext(f"{ATOM}id", "")
    m = re.search(r"abs/([^v]+)(v\d+)?$", aid)
    pdf = next(
        (l.get("href") for l in e.findall(f"{ATOM}link") if l.get("title") == "pdf"),
        None,
    )
    return {
        "source": "arxiv",
        "arxiv_id": m.group(1) if m else aid,
        "title": re.sub(r"\s+", " ", e.findtext(f"{ATOM}title", "")).strip(),
        "authors": [a.findtext(f"{ATOM}name", "") for a in e.findall(f"{ATOM}author")],
        "abstract": re.sub(r"\s+", " ", e.findtext(f"{ATOM}summary", "")).strip(),
        "published": e.findtext(f"{ATOM}published", ""),
        "updated": e.findtext(f"{ATOM}updated", ""),
        "categories": [c.get("term") for c in e.findall(f"{ATOM}category")],
        "doi": e.findtext(f"{ARXIV_NS}doi"),
        "url": aid,
        "pdf_url": pdf,
    }


def arxiv_by_id(arxiv_id):
    url = f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    root = ET.fromstring(_get(url))
    entries = root.findall(f"{ATOM}entry")
    if not entries:
        raise RuntimeError(f"arXiv ID not found: {arxiv_id}")
    return _parse_arxiv_entry(entries[0])


def arxiv_search(query, days=None, max_results=50):
    url = (
        "http://export.arxiv.org/api/query?search_query="
        + urllib.parse.quote(query)
        + f"&start=0&max_results={max_results}"
        + "&sortBy=submittedDate&sortOrder=descending"
    )
    root = ET.fromstring(_get(url))
    out = [_parse_arxiv_entry(e) for e in root.findall(f"{ATOM}entry")]
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        out = [
            p
            for p in out
            if p["updated"]
            and datetime.fromisoformat(p["updated"].replace("Z", "+00:00")) >= cutoff
        ]
    return out


# ----------------------------------------------------------------- DBLP ----


def dblp_search(query, max_results=10):
    url = (
        "https://dblp.org/search/publ/api?q="
        + urllib.parse.quote(query)
        + f"&h={max_results}&format=json"
    )
    data = json.loads(_get(url))
    hits = data.get("result", {}).get("hits", {}).get("hit", []) or []
    out = []
    for h in hits:
        i = h.get("info", {})
        raw_a = i.get("authors", {}).get("author", [])
        if isinstance(raw_a, dict):
            raw_a = [raw_a]
        out.append(
            {
                "source": "dblp",
                "dblp_key": i.get("key"),
                "title": i.get("title"),
                "authors": [a.get("text") for a in raw_a],
                "venue": i.get("venue"),
                "year": i.get("year"),
                "type": i.get("type"),
                "doi": i.get("doi"),
                "url": i.get("ee") or i.get("url"),
                "bibtex_url": f"https://dblp.org/rec/{i.get('key')}.bib",
            }
        )
    return out


def dblp_bibtex(dblp_key):
    return _get(f"https://dblp.org/rec/{dblp_key}.bib")


# ----------------------------------------------------- Semantic Scholar ----

S2_FIELDS = "title,year,venue,externalIds,abstract,citationCount,openAccessPdf,authors"


def s2_paper(pid, refs=False, cites=False):
    base = "https://api.semanticscholar.org/graph/v1/paper/"
    out = {"paper": json.loads(_get(base + urllib.parse.quote(pid) + "?fields=" + S2_FIELDS))}
    if refs:
        out["references"] = json.loads(
            _get(base + urllib.parse.quote(pid) + "/references?fields=" + S2_FIELDS + "&limit=100")
        ).get("data", [])
    if cites:
        out["citations"] = json.loads(
            _get(base + urllib.parse.quote(pid) + "/citations?fields=" + S2_FIELDS + "&limit=100")
        ).get("data", [])
    return out


# ----------------------------------------------------------------- main ----


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("arxiv");        a.add_argument("id")
    s = sub.add_parser("arxiv-search"); s.add_argument("query"); s.add_argument("--days", type=int); s.add_argument("--max", type=int, default=50)
    d = sub.add_parser("dblp-search");  d.add_argument("query"); d.add_argument("--max", type=int, default=10)
    b = sub.add_parser("dblp-bib");     b.add_argument("key")
    s2 = sub.add_parser("s2");          s2.add_argument("id"); s2.add_argument("--refs", action="store_true"); s2.add_argument("--cites", action="store_true")

    args = p.parse_args()
    try:
        if args.cmd == "arxiv":
            print(json.dumps(arxiv_by_id(args.id), ensure_ascii=False, indent=2))
        elif args.cmd == "arxiv-search":
            print(json.dumps(arxiv_search(args.query, args.days, args.max), ensure_ascii=False, indent=2))
        elif args.cmd == "dblp-search":
            print(json.dumps(dblp_search(args.query, args.max), ensure_ascii=False, indent=2))
        elif args.cmd == "dblp-bib":
            sys.stdout.write(dblp_bibtex(args.key))
        elif args.cmd == "s2":
            print(json.dumps(s2_paper(args.id, args.refs, args.cites), ensure_ascii=False, indent=2))
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
