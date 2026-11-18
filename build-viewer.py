#!/usr/bin/env python3
"""
build-viewer.py — generates the single-file offline viewer (index.html).

Reads manifest.json, checks which PDFs exist on disk under papers/, and
embeds a compact catalogue (with per-file presence flags) into
viewer-template.html, writing index.html. No network needed.

    python build-viewer.py                       # after running downloader.py
    python build-viewer.py --manifest ..\\manifest.json --out index.html
"""
import argparse
import json
import re
import sys
from pathlib import Path


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-") or "_"


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-_") or "paper.pdf"


def looks_like_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=None,
                    help="path to manifest.json (default: this folder, then ../ial-papers-v2/)")
    ap.add_argument("--subjects", default=None,
                    help="comma-separated subjects to include (default: all)")
    ap.add_argument("--papers", default="papers")
    ap.add_argument("--template", default="viewer-template.html")
    ap.add_argument("--out", default="index.html")
    args = ap.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else None
    if manifest_path is None:
        for cand in ("manifest.json", Path("..") / "ial-papers-v2" / "manifest.json"):
            if Path(cand).exists():
                manifest_path = Path(cand)
                break
    template_path = Path(args.template)
    if not manifest_path or not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    if not template_path.exists():
        print(f"template not found: {template_path}", file=sys.stderr)
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    papers_dir = Path(args.papers)
    want_subjects = None
    if args.subjects:
        want_subjects = {s.strip().lower() for s in args.subjects.split(",") if s.strip()}

    records = []
    present_count = 0
    for p in manifest.get("papers", []):
        subj = p.get("subject") or "?"
        if want_subjects and subj.lower() not in want_subjects:
            continue
        unit = p.get("unitCode") or "_"
        sess = p.get("session") or "_"
        fname = safe_filename(p.get("fileName") or "paper.pdf")
        rel = f"papers/{slugify(subj)}/{unit}/{sess}/{fname}"
        full = papers_dir / slugify(subj) / unit / sess / fname
        present = full.exists() and full.stat().st_size > 4096 and looks_like_pdf(full)
        if present:
            present_count += 1
        spec = p.get("specCode") or ""
        records.append({
            "s": subj,
            "u": p.get("unitCode"),
            "ul": p.get("unitLabel"),
            "ss": p.get("session"),
            "sl": p.get("seriesLabel"),
            "t": p.get("docType"),
            "ti": p.get("title"),
            "f": rel,
            "p": present,
            "v": p.get("variant") or "",
            "z": p.get("sizeKb"),
            "o": p.get("url") or "",
            "l": not spec.startswith("ial18-"),
        })

    catalog = {
        "generatedAt": manifest.get("generatedAt"),
        "count": len(records),
        "presentCount": present_count,
        "papers": records,
    }
    payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))

    with open(template_path, encoding="utf-8") as f:
        html = f.read()
    if "__CATALOG__" not in html:
        print("template is missing the __CATALOG__ token", file=sys.stderr)
        return 1
    html = html.replace("__CATALOG__", payload)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"catalogue entries : {len(records)}")
    print(f"PDFs on disk      : {present_count}")
    print(f"written           : {args.out} ({len(html)/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
