#!/usr/bin/env python3
"""make-dummy-pdfs.py — create placeholder PDFs for the first N catalogue
entries so you can preview the offline viewer before running the full
download. (Optional; not needed for normal use.)

    python make-dummy-pdfs.py --limit 60
"""
import argparse
import json
import re
import sys
from pathlib import Path

MINIMAL_PDF = (
    b"%PDF-1.4\n% placeholder file created by make-dummy-pdfs.py\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-") or "_"


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-_") or "paper.pdf"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--papers", default="papers")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else None
    if manifest_path is None:
        for cand in ("manifest.json", Path("..") / "ial-papers-v2" / "manifest.json"):
            if Path(cand).exists():
                manifest_path = Path(cand)
                break
    if not manifest_path or not manifest_path.exists():
        print("manifest not found", file=sys.stderr)
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    papers_dir = Path(args.papers)
    papers = manifest.get("papers", [])
    step = max(1, len(papers) // args.limit)
    sample = papers[::step][: args.limit]  # spread across subjects/sessions, not just the head
    made = 0
    for p in sample:
        dest = papers_dir / slugify(p.get("subject")) / (p.get("unitCode") or "_") / (p.get("session") or "_") / safe_filename(p.get("fileName") or "paper.pdf")
        if dest.exists() and dest.stat().st_size > 4096:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob = MINIMAL_PDF + b"% placeholder padding\n" * 220  # > 4 KB so the presence check passes
        dest.write_bytes(blob)
        made += 1
    print(f"{made} dummy PDFs written under {papers_dir}/")
    print("next: python build-viewer.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
