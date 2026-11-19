# Edexcel IAL Past Papers · Offline Edition

A **fully offline** past-paper viewer: every PDF is stored in the `papers/`
folder and opened **instantly from disk** — no network, no Pearson embedding
blocks, no waiting. QP ⇄ MS **side-by-side** mode with a draggable divider.

> The fetching edition (parent folder) is kept unchanged — this is a separate,
> self-contained build you can drop straight onto GitHub.

## Folder contents

```
ial-offline/
├── index.html            ← the whole viewer (single file, no CDN, no dependencies)
├── papers/               ← PDFs: papers/{Subject}/{unit}/{session}/{file}.pdf
├── downloader.py         ← downloads every PDF from the catalogue (resumable)
├── prune-dead.py         ← removes dead official links listed in failed.txt
├── build-viewer.py       ← regenerates index.html after downloading
├── viewer-template.html  ← template used by build-viewer.py
└── README.md
```

> **Current state of this folder:** trimmed to **Mathematics · Chemistry · Physics**
> (1,832 PDFs, ~1.5 GB, sessions through **June 2026** — 2026 sessions came from
> Paperlords since Pearson locks them). To change the set, delete other subject
> folders under `papers/` and rebuild with
> `python build-viewer.py --subjects Mathematics,Chemistry,Physics` (or no flag
> for everything).

## 1 · Download the PDFs (once)

From this folder:

```bash
python downloader.py                                    # everything (2,840 files, ~2.2 GB)
python downloader.py --subjects Mathematics,Physics,Chemistry   # core subjects (~700 files)
python downloader.py --limit 20                         # quick test
python downloader.py --threads 6                        # faster
```

- **Resumable** — re-run any time; existing complete PDFs are skipped.
- A handful of Pearson links are dead (files the board has removed over the
  years). They're listed in `failed.txt`; remove them from the catalogue with:

```bash
python prune-dead.py
```

## 2 · Build the viewer (once)

```bash
python build-viewer.py
```

This embeds the catalogue (with which files exist on disk) into `index.html`.
Open `index.html` — everything works from disk, even without internet.
**Side-by-side QP + MS** works out of the box (local files, no iframe blocks);
drag the divider between the two panes to resize.

## 3 · The locked 2026 sessions (Paperlords)

Pearson locks papers from roughly the last 9–12 months for teacher mocks
(they return HTTP 401), so the official pipeline above can't fetch them.
[Paperlords](https://www.paperlords.org) archives copies; this script pulls
only the papers your catalogue is missing (Jan/June 2026 etc.), renames them
into the standard layout, and writes `paperlords-new.json` with their
catalogue entries:

```bash
python paperlords-download.py            # query archive + download missing
python paperlords-download.py --dry-run  # just list what's missing
python build-viewer.py --subjects Mathematics,Chemistry,Physics
```

Afterwards merge `paperlords-new.json`'s `papers` into
`../ial-papers-v2/manifest.json` (bump `count`) and rebuild.

## 4 · Publish on GitHub

1. Put this whole folder in a repo, e.g.:

   ```bash
   git init
   git add -A
   git commit -m "IAL offline past papers"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```

2. On GitHub: **Settings → Pages → Source: Deploy from a branch → main → / (root) → Save**.
3. Your site: `https://<you>.github.io/<repo>/` — PDFs load instantly, and the
   side-by-side QP + MS mode works (same-origin files, no iframe blocks).

### Repo size tips

- 2,840 PDFs ≈ **2.2 GB** — a normal `git push` will be slow. If that's a
  problem, either:
  - download only the subjects you need (`--subjects …`), or
  - use Git LFS: `git lfs track "papers/**"` and commit the pointers, or
  - push the repo once and update it incrementally afterwards (each new exam
    series adds only ~100 files).

## Updating after each new exam series

1. Refresh the catalogue in the parent folder (`sync.html` or `indexer.py` + `merge-manifest.py`).
2. `python downloader.py` (downloads only the new files, skips the rest).
3. `python prune-dead.py` (removes any dead links from the catalogue).
4. `python build-viewer.py` and push.

## Notes

- Papers are © Pearson Education Ltd — local copies are for personal
  educational use.
- Papers Pearson locks for teachers (`/content/dam/secure/…`, HTTP 401) are
  not part of the catalogue, so every file here actually opens.
- The 👻 button in the viewer reveals catalogue entries whose PDFs aren't
  downloaded yet (they link to Pearson's site); hide them again with the same
  button.
