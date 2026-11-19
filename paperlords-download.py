#!/usr/bin/env python3
"""
paperlords-download.py — fetch the MISSING IAL papers (2026 sessions etc.) for
Mathematics, Chemistry and Physics from Paperlords' Supabase archive, rename
them to this project's convention and save them into papers/.

    python paperlords-download.py                # query live + download missing
    python paperlords-download.py --dry-run      # list what would download
    python paperlords-download.py --limit 10     # only the first N missing files

Outputs:
  papers/{Subject}/{unit}/{session}/{file}.pdf   (renamed, verified)
  paperlords-new.json                            (manifest entries for the merge step)

Requires Python 3.9+ (standard library only) and internet access.
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SUPABASE = "https://lldrclumayqoegzfxdcb.supabase.co"
ANON_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxsZHJjbHVtYXlxb2VnemZ4ZGNiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgxNDEwNjEsImV4cCI6MjA4MzcxNzA2MX0."
            "lb7hAjOku_mcU_-o9EJlhA-74eSpMm3U27ssoQW5c5o")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEXLET_PROXY = "https://allorigins.hexlet.app/raw?url="

SUBJECT_MAP = {"Physics": "Physics", "Chemistry": "Chemistry", "Maths": "Mathematics"}
SPEC_MAP = {"Physics": "ial18-physics", "Chemistry": "ial18-chemistry", "Maths": "ial18-mathematics"}
SCIENCE_UNITS = {"Physics": "WPH", "Chemistry": "WCH"}
MATHS_UNITS = {
    "P1": "WMA11", "P2": "WMA12", "P3": "WMA13", "P4": "WMA14",
    "M1": "WME01", "M2": "WME02", "M3": "WME03",
    "S1": "WST01", "S2": "WST02", "S3": "WST03",
    "D1": "WDM11", "FP1": "WFM01", "FP2": "WFM02", "FP3": "WFM03",
}
UNIT_LABELS = {
    "WMA11": ("P1", "Pure 1"), "WMA12": ("P2", "Pure 2"), "WMA13": ("P3", "Pure 3"), "WMA14": ("P4", "Pure 4"),
    "WME01": ("M1", "Mechanics 1"), "WME02": ("M2", "Mechanics 2"), "WME03": ("M3", "Mechanics 3"),
    "WST01": ("S1", "Statistics 1"), "WST02": ("S2", "Statistics 2"), "WST03": ("S3", "Statistics 3"),
    "WDM11": ("D1", "Decision 1"), "WFM01": ("FP1", "Further Pure 1"),
    "WFM02": ("FP2", "Further Pure 2"), "WFM03": ("FP3", "Further Pure 3"),
}
TYPE_MAP = {"QP": "QP", "MS": "MS", "ER": "ER", "PEF": "ER"}
TYPE_SUFFIX = {"QP": "que", "MS": "rms", "ER": "pef"}
TYPE_NAME = {"QP": "Question paper", "MS": "Mark scheme", "ER": "Examiner report"}
MONTH_LABEL = {"01": "January", "06": "June", "10": "October"}


def session_of(raw: str):
    m = re.match(r"^(Jan|June|MayJune|May|Oct|November|Nov)\s*(\d{4})$", (raw or "").strip())
    if not m:
        return None
    mon, year = m.group(1), int(m.group(2))
    if mon == "Jan":
        mm = "01"
    elif mon in ("June", "MayJune", "May"):
        mm = "06"
    else:
        mm = "10"
    return f"{year}-{mm}"


def science_unit_code(subject: str, num: int) -> str:
    return f"{SCIENCE_UNITS[subject]}1{num}"  # WPH11 ... WPH16 pattern


def http_get(url: str, headers: dict | None = None, timeout: int = 90) -> bytes:
    # Paperlords stores some paths with literal spaces ("June 2026") — encode them
    url = urllib.parse.quote(url, safe=":/%?&=+#$,;@~!*'")
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_metadata() -> list[dict]:
    rows: list[dict] = []
    subjects = ("Physics", "Chemistry", "Maths")
    for subj in subjects:
        query = (
            "/rest/v1/papers?select=subject,session,unit,type,link,variant"
            f"&category=eq.IAL&deleted_at=is.null&subject=eq.{subj}&limit=20000"
        )
        url = SUPABASE + query
        headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "User-Agent": UA}
        data = json.loads(http_get(url, headers=headers).decode("utf-8"))
        rows.extend(data)
        print(f"  {subj}: {len(data)} rows")
        time.sleep(0.3)
    return rows


def load_manifest() -> dict:
    for cand in (Path("..") / "ial-papers-v2" / "manifest.json", Path("manifest.json")):
        if cand.exists():
            with open(cand, encoding="utf-8") as f:
                return json.load(f)
    return {"papers": []}


def existing_keys(manifest: dict) -> dict:
    """key -> True for what the manifest already covers."""
    keys = {}
    for p in manifest.get("papers", []):
        keys[(p.get("subject"), p.get("unitCode"), p.get("session"), p.get("docType"), p.get("variant") or "")] = True
        keys[(p.get("subject"), p.get("unitCode"), p.get("session"), p.get("docType"))] = True
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="don't download, just report")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N missing files")
    ap.add_argument("--metadata-file", default=None,
                    help="use a local JSON of Supabase rows instead of querying live")
    args = ap.parse_args()

    print("== 1. metadata ==")
    if args.metadata_file:
        with open(args.metadata_file, encoding="utf-8") as f:
            rows = json.load(f)
        print(f"  loaded {len(rows)} rows from {args.metadata_file}")
    else:
        rows = fetch_metadata()

    print("== 2. mapping + diff ==")
    manifest = load_manifest()
    have = existing_keys(manifest)
    norm = []
    for r in rows:
        subj = SUBJECT_MAP.get(r.get("subject"))
        if not subj:
            continue
        session = session_of(r.get("session") or "")
        if not session:
            continue
        dtype = TYPE_MAP.get((r.get("type") or "").strip().upper())
        if dtype not in ("QP", "MS", "ER"):
            continue
        unit_raw = (r.get("unit") or "").strip()
        variant = ""
        if unit_raw not in MATHS_UNITS and unit_raw not in ("U1", "U2", "U3", "U4", "U5", "U6"):
            m = re.match(r"^(.*?)([AR])$", unit_raw)
            if m:
                unit_raw, variant = m.group(1), m.group(2)
        unit_code = None
        if subj in ("Physics", "Chemistry"):
            mm = re.match(r"^U(\d)$", unit_raw)
            if mm:
                unit_code = science_unit_code(subj, int(mm.group(1)))
        elif subj == "Mathematics":
            unit_code = MATHS_UNITS.get(unit_raw)
        if not unit_code:
            continue  # legacy C12/C34 or unknown units — skip
        norm.append({
            "subject": subj, "unitCode": unit_code, "session": session,
            "docType": dtype, "variant": variant, "link": (r.get("link") or "").strip(),
            "plSession": (r.get("session") or "").strip(),
        })

    # dedupe Paperlords rows (same paper listed twice)
    seen = set()
    uniq = []
    for n in norm:
        k = (n["subject"], n["unitCode"], n["session"], n["docType"], n["variant"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(n)

    missing = []
    for n in uniq:
        exact = (n["subject"], n["unitCode"], n["session"], n["docType"])
        vkey = (n["subject"], n["unitCode"], n["session"], n["docType"], n["variant"])
        if n["variant"]:
            # variant papers: if session >= 2026 use exact key; for older sessions
            # avoid re-downloading files we already have under a different label
            if n["session"] >= "2026":
                if vkey in have or exact in have:
                    continue
            else:
                if vkey in have:
                    continue
                # skip if any same unit/type/variant exists in 2025 (relabelled dupes)
                dup = any(
                    p.get("subject") == n["subject"] and p.get("unitCode") == n["unitCode"]
                    and p.get("docType") == n["docType"] and (p.get("variant") or "") == n["variant"]
                    and (p.get("session") or "").startswith("2025")
                    for p in manifest.get("papers", [])
                )
                if dup:
                    continue
        else:
            if exact in have:
                continue
        missing.append(n)

    print(f"  paperlords rows: {len(rows)} -> usable: {len(uniq)} -> missing: {len(missing)}")
    if args.limit:
        missing = missing[: args.limit]

    print("== 3. download ==")
    out_root = Path("papers")
    new_entries: list[dict] = []
    ok = fail = 0
    for i, n in enumerate(missing):
        y, m = n["session"].split("-")
        part = "01" + (n["variant"].lower() if n["variant"] else "")
        fname = f"{n['unitCode'].lower()}-{part}-{TYPE_SUFFIX[n['docType']]}-{y}{m}.pdf"
        dest = out_root / n["subject"] / n["unitCode"] / n["session"] / fname
        if n["unitCode"] in UNIT_LABELS:
            label, label_name = UNIT_LABELS[n["unitCode"]]
        else:
            num = n["unitCode"][-1]  # sciences: unit number is the last digit (WPH16 -> 6)
            label = label_name = f"Unit {num}"
        series = f"{MONTH_LABEL[m]} {y}"
        entry = {
            "id": "pl-" + hashlib.sha1(n["link"].encode()).hexdigest()[:16],
            "subject": n["subject"],
            "specCode": SPEC_MAP.get(n["subject"], "ial18-" + n["subject"].lower()),
            "unitCode": n["unitCode"],
            "unitLabel": label,
            "unitName": label_name,
            "session": n["session"],
            "seriesLabel": series,
            "docType": n["docType"],
            "title": f"{TYPE_NAME[n['docType']]} - {label} ({n['unitCode']}) - {series}",
            "url": urllib.parse.quote(n["link"], safe=":/%?&=+#$,;@~!*'"),
            "fileName": fname,
            "variant": n["variant"],
            "sizeKb": None,
            "locked": False,
            "source": "paperlords",
        }

        if args.dry_run:
            print(f"  [dry] {fname}")
            new_entries.append(entry)
            continue

        if dest.exists() and dest.stat().st_size > 20480 and dest.read_bytes()[:5] == b"%PDF-":
            print(f"  [skip] {fname}")
            entry["sizeKb"] = round(dest.stat().st_size / 1024, 2)
            new_entries.append(entry)
            continue

        data = None
        for attempt in range(3):
            try:
                url = n["link"]
                if "r2.dev" in url and attempt > 0:
                    url = HEXLET_PROXY + urllib.parse.quote(n["link"], safe="")
                data = http_get(url)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  [retry {attempt+1}] {fname}: {exc}")
                time.sleep(2.0 * (attempt + 1))
        if not data:
            print(f"  [FAIL] {fname}")
            fail += 1
            continue
        if not data.startswith(b"%PDF") or b"%%EOF" not in data[-2048:] or len(data) < 20480:
            print(f"  [BAD ] {fname} (not a valid PDF, {len(data)} bytes)")
            fail += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        entry["sizeKb"] = round(len(data) / 1024, 2)
        new_entries.append(entry)
        ok += 1
        print(f"  [ok  ] {fname} ({len(data)//1024} KB)  {ok + fail}/{len(missing)}")
        time.sleep(0.15)

    print(f"\n== 4. result: {ok} downloaded, {fail} failed, {len(new_entries)} entries ==")
    if new_entries:
        with open("paperlords-new.json", "w", encoding="utf-8") as f:
            json.dump({"count": len(new_entries), "papers": new_entries}, f, ensure_ascii=False, indent=2)
        print("wrote paperlords-new.json — next: run build-viewer + merge step (I'll do the merge)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
