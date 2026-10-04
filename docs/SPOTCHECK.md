# SpotCheck, Backups & Guidance

Design notes for the confirmation, backup-awareness, and in-app guidance features. These
extend the base app (see [`CONCEPT.md`](CONCEPT.md)) and share one job: **give the user
confidence and context before anything is deleted**. Everything here is advisory and
reversible.

## 1. SpotCheck

An optional confirmation step, opened on a group from Results. It shows each file at a
readable size — full image previews or document snippets — with the keeper first, so the user
can confirm the copies match before acting. It is a **gate, not an actor**: closing it changes
nothing, and any removal still confirms and defaults to Trash.

- Images: large previews, resolution/size/path, and (planned) synced zoom + A/B difference view.
- Documents and other files: a readable snippet from a read-only preview provider.
- Each candidate has a confirm checkbox; the footer shows the running decision and the same
  Trash / hard-link actions.

Implemented as `ui/pages/spotcheck.py` (`SpotCheckDialog`), opened via `window.open_spotcheck`.

## 2. Preview providers

`core/preview.py` produces a `Preview(kind, title, text, image_path, note)` for a file, chosen
by type. Providers are **read-only and never execute a file**, follow a link out, or touch the
network, and are bounded by byte/time budgets. Missing optional tools fall back to a metadata
card.

| Kind | Shows | Optional dependency |
| --- | --- | --- |
| Images | Full preview | Pillow (already used) |
| Text / code / config | First ~40 lines | none |
| PDF | First page text | `pdftotext` (poppler) or `pypdf` |
| Office (docx/odt/pptx/xlsx) | First paragraphs / sheet names | none (reads the zip XML) |
| Archives | Entry list + count | none |
| Other / binary | Type + size | none |

## 3. Backup detection & the Probable Backup marker

`core/backup_detect.py` flags likely backups by name markers (`~`, `.bak`, `.old`, `backup`,
`copy`, `vN`), embedded date stamps, backup folders, and dated sibling sets (two or more dated
files in one group). A flagged file gets a **Probable backup** badge (icon + words, not colour
alone) and a **Newest / Older** age marker. Detection never deletes; it only suggests.

## 4. Keep-newest-backup policy

When a group `has_backups`, `core/policy.py` adds a top rule: **keep the newest** (embedded
date when present, else mtime). The rest become candidates. Overridable, and switchable off in
Settings ("For backups, keep the newest").

## 5. Contextual info icons

`ui/widgets/info_hint.py` (`InfoHint(window, term_key)`) is a keyboard-focusable `(i)` button
whose popover shows a one-sentence explanation from the glossary, with a **Learn more** link
into the Knowledge page. Placed where confusion is likely — the match kind, backup badge,
Newest/Older labels, scan options, exclusion presets, and safety actions.

## 6. Scan exclusions

`core/exclusions.py` defines named presets (system, caches, build artifacts, VCS internals,
apps, stubs, trash) plus custom globs, compiled to a matcher used in `walk()`. Excluded paths
are never scanned and can never become removal candidates. Toggled in Settings → Scan scope.

## 7. Glossary / Knowledge page

`core/glossary.py` loads and searches `data/glossary/en.json` (terms, aliases, categories,
FAQ). `ui/pages/knowledge.py` is a searchable local page; info icons deep-link into it. All
local, no network. A test asserts every `InfoHint` key resolves to an entry.

## Data-model additions

`FileEntry`: `is_backup`, `backup_confidence`, `effective_date`, `is_newest`.
`DuplicateGroup`: `has_backups`. `ScanOptions`: `exclusions`, `detect_backups`,
`keep_newest_backup`. All optional with safe defaults; `core/` stays pure (guarded by
`test_purity`).

## Status

All seven implemented and covered by tests (exclusions, backup detection, previews, glossary,
plus the headless smoke test). SpotCheck previews cover images (broad format set incl. HEIC/RAW
fallback), **audio/music (inline player)**, video (inline player + poster), PDF (paged viewer),
text/office/archive snippets. Planned refinements: synced zoom and A/B difference view; custom-glob UI.
