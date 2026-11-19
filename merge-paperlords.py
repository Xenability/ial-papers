#!/usr/bin/env python3
"""
merge-paperlords.py — merge paperlords-new.json entries into the main manifest.

Dedupes by (subject, unitCode, session, docType, variant) and by filename, so
re-running is always safe.

    python merge-paperlords.py
"""
import json
import sys
from pathlib import Path


def main() -> int:
    new_path = Path("paperlords-new.json")
    man_path = Path("..") / "ial-papers-v2" / "manifest.json"
    if not new_path.exists():
        print(f"{new_path} not found — run paperlords-download.py first")
        return 1
    if not man_path.exists():
        print(f"{man_path} not found")
        return 1

    new = json.loads(new_path.read_text(encoding="utf-8"))
    m = json.loads(man_path.read_text(encoding="utf-8"))

    papers = m.get("papers", [])
    seen = set()
    for p in papers:
        seen.add((p.get("subject"), p.get("unitCode"), p.get("session"),
                  p.get("docType"), p.get("variant") or ""))
        seen.add(("file", (p.get("fileName") or "").lower()))

    added = skipped_missing = skipped_dup = 0
    for e in new.get("papers", []):
        if not e.get("sizeKb"):
            skipped_missing += 1  # never downloaded successfully
            continue
        k = (e.get("subject"), e.get("unitCode"), e.get("session"),
             e.get("docType"), e.get("variant") or "")
        if k in seen or ("file", (e.get("fileName") or "").lower()) in seen:
            skipped_dup += 1
            continue
        seen.add(k)
        seen.add(("file", (e.get("fileName") or "").lower()))
        papers.append(e)
        added += 1

    papers.sort(key=lambda p: (
        p.get("subject") or "", p.get("unitCode") or "", p.get("session") or "",
        p.get("docType") or "", p.get("variant") or "", p.get("fileName") or "",
    ))
    m["papers"] = papers
    m["count"] = len(papers)
    note = m.get("note", "")
    if "paperlords" not in note:
        note += (f" Includes {added} papers (source 'paperlords') covering Pearson-locked "
                 "2026 sessions and gaps in the official index.")
    m["note"] = note
    man_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"manifest now: {len(papers)} papers")
    print(f"  added {added}, skipped {skipped_dup} duplicates, {skipped_missing} without files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
