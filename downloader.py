#!/usr/bin/env python3
r"""
downloader.py — download every past-paper PDF from manifest.json into a local
folder so the offline viewer never needs the network again.

    python downloader.py                       # download EVERYTHING (~2,900 PDFs)
    python downloader.py --subjects Mathematics,Physics,Chemistry
    python downloader.py --threads 6           # faster (be polite: <=6)
    python downloader.py --limit 20            # test with the first 20 files

Behaviour:
  * resumable  — files that already exist AND start with "%PDF-" are skipped
  * retries    — 3 attempts per file, then the URL is logged to failed.txt
  * organised  — papers/{Subject}/{unit}/{session}/{file}.pdf
  * polite     — small delay between requests, concurrent threads

Requires Python 3.9+ (standard library only).
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TIMEOUT = 90
RETRIES = 3
DELAY = 0.05

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


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


def download_one(entry: dict, out_dir: Path, session) -> tuple:
    """Returns (status, message)."""
    raw_url = entry.get("url") or ""
    # Pearson's index stores some paths with literal spaces/parens; percent-encode them.
    url = urllib.parse.quote(raw_url, safe=":/%?&=+#$,;@~!*'")
    fname = safe_filename(entry.get("fileName") or "paper.pdf")
    dest_dir = out_dir / slugify(entry.get("subject")) / (entry.get("unitCode") or "_") / (entry.get("session") or "_")
    dest = dest_dir / fname

    if dest.exists() and dest.stat().st_size > 4096 and looks_like_pdf(dest):
        return "skip", str(dest)

    dest_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"})
    last_err = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF-"):
                last_err = f"not a PDF ({data[:12]!r})"
                time.sleep(1.0 * (attempt + 1))
                continue
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            time.sleep(DELAY)
            return "ok", f"{len(data)//1024} KB"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(1.5 * (attempt + 1))
    return "fail", last_err or "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Download all past-paper PDFs from manifest.json")
    ap.add_argument("--manifest", default=None,
                    help="path to manifest.json (default: this folder, then ../ial-papers-v2/)")
    ap.add_argument("--out", default="papers", help="output folder (default: papers)")
    ap.add_argument("--subjects", help="comma-separated subjects to download (default: all)")
    ap.add_argument("--units", help="comma-separated unit codes to download (default: all)")
    ap.add_argument("--sessions", help="comma-separated sessions e.g. 2025-10 (default: all)")
    ap.add_argument("--threads", type=int, default=4, help="concurrent downloads (default 4, max ~6)")
    ap.add_argument("--limit", type=int, default=0, help="download only the first N matching files")
    args = ap.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else None
    if manifest_path is None:
        for cand in ("manifest.json", Path("..") / "ial-papers-v2" / "manifest.json"):
            if Path(cand).exists():
                manifest_path = Path(cand)
                break
    if not manifest_path or not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    papers = manifest.get("papers", [])
    if args.subjects:
        want = {s.strip().lower() for s in args.subjects.split(",") if s.strip()}
        papers = [p for p in papers if (p.get("subject") or "").lower() in want]
    if args.units:
        want = {u.strip().upper() for u in args.units.split(",") if u.strip()}
        papers = [p for p in papers if (p.get("unitCode") or "").upper() in want]
    if args.sessions:
        want = {s.strip() for s in args.sessions.split(",") if s.strip()}
        papers = [p for p in papers if (p.get("session") or "") in want]
    if args.limit:
        papers = papers[: args.limit]

    out_dir = Path(args.out)
    total = len(papers)
    est = sum(p.get("sizeKb") or 400 for p in papers) / 1024.0
    print(f"{total} files to process (est. {est:.1f} MB) -> {out_dir.resolve()}")
    print(f"threads={args.threads}, resume enabled, retries={RETRIES}")
    print("-" * 60)

    counts = {"ok": 0, "skip": 0, "fail": 0}
    failed: list[tuple[str, str]] = []
    t0 = time.time()
    done = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as pool:
        futures = {pool.submit(download_one, p, out_dir, None): p for p in papers}
        for fut in concurrent.futures.as_completed(futures):
            entry = futures[fut]
            try:
                status, msg = fut.result()
            except Exception as exc:  # noqa: BLE001
                status, msg = "fail", str(exc)
            counts[status] += 1
            done += 1
            if status == "fail":
                failed.append((entry.get("url") or "", msg))
            if done % 25 == 0 or done == total:
                el = time.time() - t0
                rate = done / el if el else 0
                log(f"[{done}/{total}] ok={counts['ok']} skip={counts['skip']} fail={counts['fail']} ({rate:.1f}/s, {el:.0f}s)")

    if failed:
        with open("failed.txt", "w", encoding="utf-8") as f:
            for url, msg in failed:
                f.write(f"{url}\t{msg}\n")
        print(f"\n{len(failed)} failures written to failed.txt (re-run to retry)")

    print(f"\nDone in {time.time()-t0:.0f}s — {counts['ok']} downloaded, {counts['skip']} already present, {counts['fail']} failed.")
    print("Next step: python build-viewer.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
