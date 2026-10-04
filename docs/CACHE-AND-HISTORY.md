# LinFileDedup — Fingerprint Cache & Scan History

The single source of truth for how LinFileDedup **remembers** what it has scanned, how that memory
**changes future scans**, and how it **persists**. This is a behavioural spec; the engineering
detail lives in the modules it names, and the user-facing summary is in
[`FEATURES.md`](FEATURES.md) §4b/§4c.

> **One sentence:** every scan writes down each file's fingerprint; the next scan screens each file
> by **size + modified-date** and, if it is unchanged, **reuses the stored result without reading
> the file at all** — which is what makes a repeat scan fast. Correctness is never traded away:
> anything new or changed is read and verified, and removals go to Trash by default.

---

## 1. What is remembered — three stores

All three live under the XDG state directory
(`$XDG_STATE_HOME`, default `~/.local/state`) in `com.mensuramedia.linfilededuplication/`. They are
tolerant JSON: a missing, empty or corrupt file is treated as "no memory", never an error.

| Store | File | Module | Holds | Cap |
| --- | --- | --- | --- | --- |
| **Content fingerprint cache** | `hashcache.json` | `core/hashcache.py` | each file's SHA-256 + change-detection fields | 300,000 |
| **Perceptual image cache** | `phashcache.json` | `core/phashcache.py` | each image's pHash + dHash + pixel size | 200,000 |
| **Scan performance log** | `scanruns.json` | `core/scanstats.py` | one record per scan: timing, counts, per-source drive specs | 50 |

A fourth file, `history.json` (`config/history.py`), is **not** part of the cache — it logs
confirmed *removals* (Trash / Delete / Hard-link) for the History page's "last cleanup" card. The
three above are the **scan memory**; `history.json` is the **action memory**.

### 1.1 Content fingerprint cache (`hashcache.json`)

Maps each file's **full path** to its fingerprint:

```
"<absolute path>"  →  [ dev, ino, size, mtime, sha256 ]
```

- **`sha256`** — the content digest the dedup comparison actually uses. (Identity is *content*, not
  filename.)
- **`size`, `mtime`** — the change-detection fields: the comparison matches on these.
- **`dev`, `ino`** — filesystem id and inode, **stored for reference but no longer required to
  match** (see §3).

Only files that reach the hashing step are recorded — i.e. files that share an exact byte **size**
with at least one other file (a collision candidate). A file unique in size can never be an exact
duplicate, so it is never hashed and never cached.

### 1.2 Perceptual image cache (`phashcache.json`)

```
"<absolute path>"  →  [ size, mtime, phash_hex, dhash_hex, [w, h] ]
```

Recorded for **every image** scanned when *Find image near-duplicates* is on (not just size
collisions), because perceptual matching compares images that are *similar*, not byte-identical.
`w, h` (pixel dimensions) feed the keep-highest-resolution policy.

### 1.3 Scan performance log (`scanruns.json`)

One `ScanRun` per completed scan (newest first), each with the totals and a `SourceStat` per
source:

```
ScanRun:    when, duration, tier, cancelled, used_cache,
            total_files, total_hashed, total_reused, groups, reclaimable_bytes, sources[]
SourceStat: path, files_scanned, files_hashed, files_reused, bytes_scanned,
            drive{ model, kind(SSD/HDD), transport, fstype, size_bytes, … }   # core/driveinfo.py
```

This is read-only memory about *performance*; it never affects what a scan finds. It powers the
Scan-page **✓ Cached** badge and the History **Recent scans** list.

---

## 2. The rule for remembering (hit / miss / update)

For every file that reaches the hashing step, the cache answers one question — *does this file need
reading?* — by comparing the live file against its stored record:

| Case | Condition | Result |
| --- | --- | --- |
| **New** | path not in the cache | **miss** → read & hash now; **record** it |
| **Changed** | path cached, but **size or mtime differs** | **miss** → re-read & re-hash; **update** the record |
| **Unchanged** | path cached, **size and mtime match** | **hit** → **reuse** the stored digest; **do not read the file** |

The perceptual cache (§1.2) uses the identical size+mtime rule for images.

So the index is **self-maintaining**: every scan reuses unchanged files and writes back anything
new or changed, keeping the memory current for next time. Nothing has to be rebuilt by hand.

---

## 3. Why the match is size + mtime (and not dev/ino)

The change-detection key is deliberately **size + mtime**. `dev` (device id) and `ino` (inode) are
stored but **not required to match**, because they are *not stable across mounts*:

- A **removable drive remounted** usually gets a new `st_dev`.
- **exFAT / NTFS** (common on USB and Windows-formatted drives) do not preserve inode numbers.

If the match required `dev`/`ino`, **every file on an external drive would miss the cache on each
remount** and be re-hashed — defeating the whole feature on exactly the drives people dedup most.
Matching on size+mtime (which the filesystem *does* preserve across remounts) is what makes a
repeat scan of a USB/external drive fast. The safety cost of this relaxation is covered in §6.

---

## 4. How the memory changes a future scan

A scan screens by the index **first**, before any file is opened. The pipeline
(`core/scanner.find_exact_groups`) for each size-collision bucket:

1. **Screen by the index.** Each file is checked against the cache. A **hit** (unchanged) takes its
   SHA-256 straight from the index — **no read at all**, not even the cheap 64 KB prefix hash.
2. **Read only the misses.** New/changed files are read: prefix-hashed to split the bucket, then
   full-hashed; each result is written back to the cache.
3. **Group by digest.** Cached hits and freshly-hashed misses are grouped together by SHA-256.
4. **Verify selectively** (see §5).

So on a repeat scan where nothing changed, a candidate file costs only a **single `stat`** (to read
its size+mtime during the directory walk) — no content read of any kind. Measured directly: a
second scan of unchanged files performs **zero** full hashes, prefix hashes and byte-verifies, yet
still finds every group (`tests/core/test_scanner.py::test_repeat_scan_skips_unchanged_files`).

**Images** follow the same path: an unchanged image reuses its stored pHash/dHash instead of being
re-opened and re-hashed (`core/image_perceptual.find_similar_groups` with the perceptual cache).

**New or newly-added sources** are always scanned — a path not in the index is a miss by
definition, so adding a drive or a folder never skips its contents.

**Multi-source / cross-drive.** The key is the **full path** (including the source root), so the
same relative file on two sources is tracked as two independent entries. This does **not** weaken
cross-source dedup: duplicates are still grouped by **content SHA-256**, so the same bytes on a disk
and a backup drive form one group regardless of path — the cache only decides whether each copy
needs re-reading.

---

## 5. Byte-verify policy

Byte-for-byte verification is the final safety check that two files really are identical before a
group is trusted. With the index, it runs **selectively**:

- A group that contains **any file read this run** (new or changed) is **byte-verified** in full —
  newly-introduced duplicates are always confirmed.
- A group whose members were **all unchanged since they were indexed** is **trusted from the stored
  digests with no re-read** — the index *is* the comparison. Re-reading them would only re-confirm
  what was already confirmed when they were first hashed, which is the cost the cache exists to
  avoid.

This is the behaviour that delivers the speed-up; its one residual risk is in §6. To restore the
old "always read and verify every file" behaviour, turn **Reuse hashes for unchanged files** off in
Settings → Scanning (then no cache is used and every file is read every scan).

---

## 6. Correctness & safety

- **New/changed files are never trusted blindly** — they are read, hashed and byte-verified (§5).
- **The one heuristic is `mtime`.** A file whose content changed while keeping **both** its size
  and its mtime identical to a previous scan would let a stale digest stand. This is pathological
  (ordinary edits change mtime, and holding byte-size constant as well is rare), a SHA-256 collision
  is effectively impossible, and the backstop is decisive: **removals go to Trash by default, so
  even that case is fully recoverable.**
- **The cache never invents equality.** It only ever reuses a digest that an earlier read computed;
  it cannot make two different files look equal without a byte-verify (for fresh files) or the
  size+mtime+SHA coincidence above (for trusted ones).
- **Trusted, shared memory only in the sense of this machine.** Nothing is transmitted; the files
  live in the user's home directory and never leave it.

---

## 7. How it persists

- **Written at the end of every scan.** `HashCache.save()` and `PHashCache.save()` run after the
  scan completes — **including when the scan is cancelled**, so a Stop still banks every fingerprint
  computed before it. The `ScanRun` is recorded when the scan finishes (`window._on_scan_finished`).
- **Survives app restart and system reboot.** They are plain files in `~/.local/state`; closing the
  app or rebooting does not touch them. (Relaunching the app does **not** rebuild or warm the cache
  — it is simply loaded from disk at the start of the next scan.)
- **Bounded growth.** Each store is capped (§1); when the cap is exceeded, the oldest entries *by
  write order* are dropped on save. At typical sizes the content cache is tens of MB.
- **No time-based expiry.** Entries live until the file is deleted, trimmed by the cap, invalidated
  by a removal (§8), or overwritten because the file changed.

---

## 8. Invalidation & lifecycle

- **After a dedup operation**, the files that were Trashed or hard-linked are dropped from **both**
  caches — `HashCache.remove()` and `PHashCache.remove()`, called from
  `ui/pages/results.py::_invalidate_cache` — so the next scan's memory stays truthful and a removed
  path never lingers as a ghost fingerprint.
- **Changed files** are not removed but **overwritten** with their new fingerprint on the scan that
  re-reads them.
- **Moved / renamed files** change their path, which is the key, so they are seen as **new** (a
  miss) at the new path and re-hashed once; the old path's entry becomes dead weight until the cap
  trims it. (Identity is still content, so a move does not break duplicate detection — it only costs
  one re-hash.)
- **Deleting a store** (e.g. `rm ~/.local/state/com.mensuramedia.linfilededuplication/hashcache.json`)
  simply makes the next scan a cold one; it is always safe.

---

## 9. What the user sees

- **Scan page — `✓ Cached` badge.** Every source with a prior scan on record shows the green pill;
  its tooltip lists the last run's time, files fingerprinted, % reused, duration and drive. The
  badge reads the small performance log, **not** the large hash cache, and is strictly read-only.
- **History — Recent scans.** Each scan's performance (time, duration, throughput, files, % reused,
  groups) with the per-source drive specs.
- **Post-scan toast.** On completion: *"… · fingerprints saved for faster re-scans."*
- **Settings → Scanning — Reuse hashes for unchanged files.** The master switch (default on). Off =
  no cache, every file read every scan.

---

## 10. Enforced by tests

| Rule | Test |
| --- | --- |
| Unchanged → hit; changed/new → miss | `tests/core/test_hashcache.py::test_hit_only_when_unchanged` |
| Remount tolerance (dev/ino ignored) | `test_hashcache.py` (dev/ino changed → still a hit); `test_phashcache.py` |
| A repeat scan reads nothing | `tests/core/test_scanner.py::test_repeat_scan_skips_unchanged_files` |
| New/changed re-hashed, unchanged reused; index self-updates | `test_hashcache.py::test_new_files_hashed_and_changed_files_update_the_cache` |
| Removal drops entries from the cache | `test_hashcache.py::test_roundtrip_and_remove` |
| Performance log round-trips / caps / per-source lookup | `tests/core/test_scanstats.py` |
| Drive probe degrades without `lsblk` | `tests/core/test_driveinfo.py` |

---

## 11. FAQ

- **I re-scanned the same external drive and it wasn't faster — why?** Before the size+mtime fix
  (§3) a remount changed `dev`/`ino` and missed the whole drive. With the fix, the **first** scan
  after upgrading still re-reads anything whose record is absent or whose mtime differs, but
  unchanged files now hit. Check **History → Recent scans → % reused** to confirm the cache is
  hitting.
- **Does the walk get cached?** No. Listing and `stat`-ing files is required to know their
  size+mtime and cannot be skipped; it is metadata only (fast). The cache removes the *content
  reads*, which are the expensive part.
- **Is anything sent anywhere?** No. All three stores are local files; nothing is transmitted.
- **Can the cache cause a wrong deletion?** For new/changed files, no — byte-verify guards them. For
  the pathological size+mtime-preserving edit (§6), the Trash default keeps it recoverable.
