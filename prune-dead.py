#!/usr/bin/env python3
"""
prune-dead.py — remove catalogue entries whose URLs failed to download
(dead links, listed in failed.txt by downloader.py).

Prunes both:
  * the main manifest (../ial-papers-v2/manifest.json by default), and
  * bootstrap-temp.json (so future merge runs don't re-introduce dead legacy links).

    python prune-dead.py
    python prune-dead.py --failed failed.txt --manifest ..\\ial-papers-v2\\manifest.json
"""
import argparse
import json
import sys
from pathlib import Path


def resolve(path: str | None, candidates: list[str]) -> Path | None:
    if path:
        p = Path(path)
        return p if p.exists() else None
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    return None


def prune(manifest_path: Path, dead: set[str], is_bootstrap: bool = False) -> int:
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    papers = data.get("papers", [])
    kept = [p for p in papers if (p.get("url") or "") not in dead]
    removed = len(papers) - len(kept)
    if removed:
        data["papers"] = kept
        data["count"] = len(kept)
        if not is_bootstrap and "note" in data and "pruned" not in data["note"]:
            data["note"] += (
                f" Pruned {removed} dead official links (files Pearson has removed; "
                "verified via downloader)."
            )
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{manifest_path}: removed {removed} of {len(papers)}")
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--failed", default="failed.txt")
    ap.add_argument("--manifest", default=None,
                    help="default: ../ial-papers-v2/manifest.json")
    ap.add_argument("--bootstrap", default="../ial-papers-v2/bootstrap-temp.json")
    args = ap.parse_args()

    failed_path = Path(args.failed)
    if not failed_path.exists():
        print(f"{failed_path} not found — nothing to prune")
        return 0

    dead = set()
    with open(failed_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                dead.add(line.split("\t")[0])

    manifest_path = resolve(args.manifest, ["../ial-papers-v2/manifest.json", "manifest.json"])
    if not manifest_path:
        print("manifest.json not found", file=sys.stderr)
        return 1
    prune(manifest_path, dead)

    boot = Path(args.bootstrap)
    if boot.exists():
        prune(boot, dead, is_bootstrap=True)

    print(f"pruned {len(dead)} dead URLs from the catalogue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
