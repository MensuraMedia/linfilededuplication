# LinFileDedup GUI Guide and Design Reference

> **About this copy.** Adapted on 2026-10-04 for **LinFileDedup** from the house design
> reference *"LinPrinter GUI Guide and Design Reference"* (MensuraMedia `linapptemplate`,
> `docs/design/GUI-GUIDE-AND-DESIGN-REFERENCE.md`, rev. 17, written 2026-10-02). That document
> states its "laws, principles, regulations, components, voice and checklist apply to every Lin\*
> app"; this file carries those forward and re-casts every app-specific part for a **scan-and-
> delete** tool, where the stakes are destructive actions and trust rather than printing. It is
> the in-tree **design source of truth** for the UI; it feeds the roadmap in
> [../CONCEPT.md](../CONCEPT.md) §8. Changes to the real app still go through the normal process:
> a plan, approval, changelog and tests.

## 1. Purpose and scope

This reference specifies LinFileDedup's interface against the ten UX laws, the ten 2026 design
principles, and the WCAG 2.2 AA accessibility baseline. Designers work from sections 7–12
(architecture, flows, tokens, theme, components, page specs); reviewers judge every screen and
mockup against sections 4–6 and the checklist in section 14.

It combines four inputs: the app as it ships today, the single governing risk of a file-dedup
tool (**deleting the wrong or only copy**), the ten UX laws and ten 2026 design principles, and
the accessibility and consumer-protection rules in force as of October 2026.

Out of scope (v1, per [../CONCEPT.md](../CONCEPT.md) §1): cloud/remote sources, audio/video
fingerprinting, inline (write-time) dedup, cross-volume global indexing, and any AI feature.

## 2. Users, jobs and context

LinFileDedup serves one person reclaiming disk space on their own machine and external drives,
and the design optimises for **removing duplicates without ever losing a file that mattered**.

| User | What they need most | What hurts them |
| --- | --- | --- |
| Space reclaimer (primary) | See what's duplicated, trust it's safe, delete it, know what was freed | Fear of deleting the only copy; bulk actions with no way to look first |
| Photo keeper | Keep the full-resolution original, cull resized/re-compressed copies | Near-duplicates judged by eye; which copy is "best" is unclear |
| Multi-drive user | Dedup a disk against a USB backup; keep the copy on the main disk | Not knowing a scan spans drives, or which copy will be kept |
| Accessibility users (keyboard, screen reader, low vision, tremor) | Full keyboard flow, large targets, status in words not colour | Keep/delete shown mainly by colour; selection flows that need the mouse |

Jobs to be done, in order of frequency:

1. Scan a folder or drive and see duplicate groups.
2. Confirm a group really is duplicate **before** removing anything.
3. Reclaim space: Trash the extra copies (or hard-link to keep references working).
4. Keep the right copy (highest-resolution original; the copy on the primary drive).
5. Dedup one source against another (disk vs. backup).
6. Exclude noise and set usual defaults once; review what was skipped.

Fixed constraints the design must respect (from `CLAUDE.md` and [../CONCEPT.md](../CONCEPT.md)):

- Debian 12/13 + Linux Mint; GTK 4 + libadwaita; distro packages only; works fully offline.
- **Local-first:** embedded icons, system fonts, stdlib + PyGObject; optional libs (Pillow,
  imagehash, xxhash, TLSH) are runtime-detected and degrade gracefully.
- **No network, no telemetry, no accounts, no AI.** Nothing leaves the machine.
- **The engine never blocks the UI:** all scanning is on a worker thread; results stream in.
- **Nothing is removed without an `Adw.AlertDialog` confirmation; Trash by default; protected
  paths refused; a group's keeper is never deletable; byte-verify before a group is trusted.**

## 3. Audit of the current app

The engine is strong and honest and the safety model is sound; the interface is organised around
the user's jobs (scan → review → reclaim → look after). The gaps are mostly in the accessibility
and status-in-words layer, which section 14 turns into a checklist.

| Page today | What it does | Main UX observations |
| --- | --- | --- |
| Overview | Entry stats and quick start | Good front door; keep it a one-glance summary |
| Scan | Sources (folders/drives), Simple/Advanced tier, image toggle, hidden, min size, file-type filter + exclusions, per-source rings, Cached badges | Dense but grouped one-concern-per-card; "Start scan" is top-right and fixed on the tier row (Fitts); file-type/exclusion sections already collapse the long tail (Hick) |
| Results | Duplicate groups as aligned rows (name · size · path · keep/delete marker), SpaceChart, Delete All Duplicates / Hard-link, SpotCheck, Ignore | Keeper (green check-circle) vs candidate (red checked box) read by **shape+colour**; add a word so status isn't colour-dependent (1.4.1) |
| SpotCheck | Large side-by-side content comparison (image/text/PDF/office/video) before a destructive action | The "look first" safety moment; the single most important screen for trust |
| Ignored | Files/folders/extensions the user chose to skip, each with Resume | Clear; it keeps the skip lists honest and reversible |
| History | Last cleanup with before/after bars + "You saved N GB"; **Recent scans** performance log with per-source drive specs | Strong end-moment; the performance log also answers "will a re-scan be fast?" |
| Settings | Theme (libadwaita), scan scope presets, backup policy, hash-cache + keep-primary toggles, default action | Reasonable; ensure every toggle states its effect in one line |
| Knowledge | Searchable glossary + FAQ, feeding InfoHint (i) icons | Recognition-over-recall done well; keep terms plain |

The governing lesson, turned into interface — **the dedup equivalent of "a cable nobody checked
first":** the costly failure is deleting a file the user still needed. So the design leads with the
cheapest reversible check (read-only scan), makes the user **look before acting** (SpotCheck),
**verifies identity byte-for-byte** before trusting a group, **never deletes the keeper**, defaults
to **Trash (recoverable)**, and records **what was removed and what was freed**. Automation
(keep/delete policy, cross-drive hard-link disabling) is always visible, scoped and overridable.

## 4. The ten UX laws, applied

Each law is used at the strength of its evidence: Fitts and Gestalt set hard rules; Hick, Miller
and the Doherty Threshold only guide.

| Law | Evidence | Rule for LinFileDedup |
| --- | --- | --- |
| Fitts's Law | Strong | Primary action is the largest, fixed target (Start scan, top-right on the tier row; Delete All Duplicates / Hard-link prominent on Results). Destructive confirm buttons sit **away** from benign ones. Every target ≥ 32 px; frequent ones 40 px. |
| Hick's Law | Narrow | Not a reason to count items. Justifies progressive disclosure: two tiers (Simple / Advanced); the long file-type/exclusion lists and "Built-in file rules" collapse by default. |
| Jakob's Law | Observation | Follow GNOME/Nautilus/Adwaita vocabulary: **Trash** (not "delete"), folder chooser, header bar, Ctrl+Q quit, Alt+1…9 to switch page, Esc closes dialogs. |
| Miller's Law | ~4 chunks (Cowan), not "7 items" | Never make the user hold identity in their head across screens: SpotCheck shows the files **side by side**; Results restate name, size and path on every row; group headers summarise. At most four visible option clusters on Scan before the collapse. |
| Tesler's Law | Sound | The system absorbs complexity: size→progressive→SHA-256→byte-verify, perceptual images, chunking/fuzzy/metadata, the hash cache, cross-drive hard-link handling. Users see outcomes ("These are identical — byte-verified"), not mechanisms ("prefix xxHash bucket, SHA-256 digest"). |
| Doherty Threshold | Directionally right | Every click acknowledges within 100 ms. The scan streams per-source percentage rings; the ring fills to 100%, holds, fades, then results appear — progress is always visible for work over ~1 s. |
| Peak-End Rule | Solid in psychology | Design the two moments that matter: the **error peak** (almost deleting the wrong file → SpotCheck + byte-verify + a naming confirmation + Trash recoverability) and the **end** (History's "You saved N GB", the post-scan "fingerprints saved" toast). |
| Aesthetic-Usability Effect | Small studies | A bias to test against, not a goal: usability checks run on plain layouts so a polished dark theme can't mask a confusing flow. |
| Postel's Law | Engineering principle | Accept any reasonable source: folders, mounted drives (incl. NTFS/exFAT with `$RECYCLE.BIN` excluded), several at once. Send only **validated** destructive operations: byte-verify first; refuse protected paths; auto-disable hard-link across filesystems. |
| Gestalt | Well established | One card per concern (Sources, Options, File types, Exclusion; one card per duplicate group). Same control type for the same choice. Status sits next to the file it describes. |

## 5. The ten 2026 design principles, applied

LinFileDedup has no AI, so the three AI principles apply to its **automation** — anything the app
does on the user's behalf (choosing the keeper, disabling cross-drive hard-link, excluding system
folders) is visible, scoped, confirmable and reversible.

| Principle | How LinFileDedup applies it |
| --- | --- |
| Accessibility by default | Designed in from the first screen: keyboard order, focus rings, screen-reader names, 4.5:1 text contrast, **no colour-only status**, targets ≥ 24×24 px (WCAG 2.2) and 32 px in practice. |
| Clear AI disclosure | Not applicable — there is no AI and no generated content. Settings/About says so plainly. |
| Human control over automated actions | Nothing is removed without explicit confirmation. The keep/delete policy is a **recommendation the user can override**; the keeper is never deletable. Cross-filesystem hard-link is disabled with its reason ("can't hard-link across drives — these will go to Trash"). |
| Honest uncertainty | **Identical** (byte-verified) and **near-duplicate / SIMILAR** are named differently and never conflated; similar groups carry their threshold. Unreadable files are reported, never silently treated as removable. |
| No dark patterns | No nagging, no fake urgency, no pre-selected permanent-delete. Backup/"older copy" markers inform; they never shame or block. |
| Easy exit | **Stop** is as visible as Start while a scan runs. Every dialog has Cancel and Esc. Leaving Settings never asks "are you sure?". |
| Error prevention over error messages | Scans are read-only; only offer what's possible (disable hard-link across filesystems, with the reason); byte-verify before a group is trusted; **confirm only destructive actions**, naming counts and what's kept. |
| Recognition over recall | SpotCheck shows the actual files; Results show name + path + size; History shows what was scanned and freed; the **✓ Cached** badge shows a source was scanned before; InfoHint (i) explains terms in place. |
| Consistency | One keep/delete vocabulary and marker everywhere; Trash metaphor throughout; GTK 4 + libadwaita platform conventions; window controls top-right. |
| Performance as UX | The hash cache reuses unchanged fingerprints; per-source rings report true progress; the pipeline is cheap-to-expensive; spinners show only while real work runs, never as decoration. |

## 6. Regulatory and accessibility baseline

Target: **WCAG 2.2 Level AA**, applied to desktop software via WCAG2ICT and EN 301 549. Legally
required for few of LinFileDedup's users, but it is the right bar and the app is built to it.

| Rule (as of October 2026) | Applies to LinFileDedup? | What the design does |
| --- | --- | --- |
| WCAG 2.2 AA | The working standard; adopted as the target | Every criterion in the next table |
| US ADA Title II / III | Only if a government deploys it / lawsuits | AA conformance covers it |
| European Accessibility Act (EN 301 549) | A free desktop utility isn't a listed product | Built to EN 301 549 anyway |
| EU AI Act, Article 50 | No — no AI system | Settings/About states there is no AI |
| GDPR / ePrivacy | No personal data leaves the machine | Local-only logs; redacted paths in diagnostics; nothing transmitted |
| Dark-pattern / subscription rules | No subscriptions, not an online platform | Principle adopted voluntarily (section 5) |

WCAG 2.2 criteria that shape these screens most:

| Criterion | Requirement in LinFileDedup |
| --- | --- |
| 1.4.1 Use of Color | **Keeper vs candidate** carries an icon **and a word** ("Keep" / "Delete"), not colour alone; the ✓ Cached badge reads in text |
| 1.4.3 / 1.4.11 Contrast | Text 4.5:1 (large 3:1); control borders, focus rings, chart outlines 3:1 — audited in **both** light and dark |
| 1.4.4 / 1.4.10 Resize & reflow | Usable at 200% text and at the 640 px minimum window without horizontal scrolling |
| 2.1.1 Keyboard | Every function by keyboard: scan, select, SpotCheck, confirm; documented shortcuts; no trap in SpotCheck/preview |
| 2.4.7 / 2.4.11 Focus visible, not obscured | 2 px focus ring at 3:1; a sticky action bar never covers the focused control |
| 2.5.8 Target size | ≥ 24×24 px; LinFileDedup's floor is 32 px |
| 3.3.1 / 3.3.3 Errors & suggestions | Each error names the **file** or **path** and the fix ("Can't read X — check permissions") |
| 3.3.4 Error prevention (destructive) | Deletions are confirmed, reversible (Trash) by default, and byte-verified first |
| 4.1.2 / 4.1.3 Name/role/value, status messages | Every control has an accessible name; scan progress, group counts and completion are announced without moving focus |

The legal summary is carried from the house brief and **hasn't been independently checked** —
confirm before any compliance claim is published.

## 7. Information architecture

LinFileDedup's navigation is organised around the user's jobs: **start** (Overview), **do the
work** (Scan → Results, with SpotCheck as the look-first overlay), **look back** (History,
Ignored), **learn** (Knowledge), **configure** (Settings). This is a reasonable seven-item rail;
the design keeps each destination a single job and resists adding more.

A persistent **sidebar** (212 px) carries the destinations with Phosphor `-symbolic` icons;
Settings sits at the bottom. Scan and Results are the spine: a scan on Scan flows to Results when
it completes, and SpotCheck opens over Results. Review whether **Ignored** and **History** could
share one "Activity"-style home in a later pass (an open question for testing, not a v1 change).

## 8. Core flows and interaction patterns

The dedup flow is **read-only until the user commits**, makes the user **look before acting**, and
**never removes a file without naming what goes and what stays**.

**The destructive-action safety ladder — cheapest-reversible first.** This is the dedup analogue
of a troubleshooter: each rung lowers the chance of losing a file that mattered, and the design
walks every removal down it.

1. **Scan is read-only.** Nothing on disk changes while finding duplicates.
2. **A keeper is chosen, and is never deletable.** Policy (section 5 of CONCEPT) picks the
   highest-resolution original / primary-source copy; the user can change the keeper.
3. **SpotCheck — look first.** Large side-by-side comparison of the actual content before any
   destructive action; the trust moment.
4. **Byte-for-byte verify.** A group is trusted only after the bytes match, so a hash collision or
   a mtime-preserving edit can never cause a wrong removal.
5. **Guards.** Protected paths are refused; cross-filesystem hard-link is auto-disabled (routes to
   Trash) with its reason shown.
6. **Named confirmation.** An `Adw.AlertDialog` states the count, the action, and what is kept; the
   file list is scrollable and un-wrapped.
7. **Trash by default (recoverable).** Permanent delete is a separate, explicitly-confirmed choice.
8. **Record it.** History shows what was scanned, what was removed, and "You saved N GB".

Patterns used across the app:

- **Progressive disclosure:** Simple vs Advanced tier; file-type and exclusion lists, and
  "Built-in file rules", collapse by default and remember being open.
- **Streaming feedback:** per-source percentage rings during a scan; results buffer and appear only
  after the ring completes and fades, so the end reads as "done".
- **Inline status, one vocabulary:** a file is **Keep** or **Delete**; a source is **✓ Cached** or
  not; a group is **Identical** or **Similar** — same words and markers in every place.
- **Automation by consent:** the keep/delete policy is a recommendation; cross-drive hard-link
  disabling and system/recycle-folder exclusion state their scope and are reversible (Ignored).
- **Undo where possible, confirm where not:** Trash is the reversible default; permanent delete and
  hard-link are named-button confirmations.
- **Keyboard first:** Ctrl+Q quit; Alt+1…9 switch destination; Esc closes dialogs/SpotCheck;
  (roadmap) full keyboard selection and SpotCheck navigation.

## 9. Visual design system

The app uses **GTK 4 + libadwaita**, so colour comes from Adwaita's named roles and the app's
accent; a theme changes values, never structure. Tokens live in `data/css/app.css` on top of
libadwaita's `@…` colours.

**Colour roles** (Adwaita names in parentheses; audited per theme in section 10):

| Role | Use | Minimum contrast |
| --- | --- | --- |
| window background (`@window_bg_color`) | App ground; the main area is a step darker than the sidebar | — |
| surface (`@card_bg_color`, `.app-card`) | Cards, dialogs, popovers | Border 3:1 where the edge carries meaning |
| border (`alpha(@window_fg_color, .08–.12)`) | Dividers, control outlines | 3:1 for control outlines |
| text / muted (`@window_fg_color`, `.app-dim`) | Body / secondary | 4.5:1 on surface for both |
| accent (`@accent_bg_color` = **#3584e4**) | Primary action, selection | 4.5:1 text on accent; accent 3:1 on surface |
| focus | Focus ring, 2 px + 2 px offset | 3:1 against adjacent colours |
| keep / delete (`@success_color` ≈ **#2ec27e** / `@error_color`) | Keeper vs candidate; Success/Failed chips | Icon **and word** paired; 4.5:1 |

**Type** (system UI font — **Cantarell** on GNOME; tabular figures for numbers):

| Token (class) | Size / line height | Weight | Use |
| --- | --- | --- | --- |
| savings head (`.app-savings-head`) | ~27 / — | 800 | "You saved N GB" hero on History |
| page title | 20 / 28 | 700 | Page headings |
| group title (`.app-group-title`) | 16 / 24 | 600 | Card titles |
| body | 14 / 21 | 400 | Everything else |
| small / mono (`.app-small`, `.app-mono`) | 12–13 | 400 | Paths, metadata; monospace for paths; never below 12 |

**Space, shape, size:** 4 px spacing base (4, 8, 12, 16, 24); cards pad ~16; page margins ~18–24;
radius ~10–14 for cards/dialogs, chips fully rounded; control heights 32 standard / 40 frequent;
minimum window **640×540**, two-pane layouts collapse to one column when narrow; elevation via
border + tint first, shadow second (so a high-contrast theme survives).

**Icons:** **Phosphor `-symbolic`** SVGs, embedded under `data/icons/`, named `app-<id>-symbolic`
(+ `-active` for the current nav item); never the system icon theme. Every icon has a text label or
accessible name.

**Motion:** ~120 ms for state changes, ~200 ms for panels/dialogs, none for status text; honour
reduce-motion (transitions become instant). The only looping animation is the scan ring while real
work runs.

## 10. Theme direction

LinFileDedup follows **libadwaita's light/dark** preference (Settings → Theme: Follow system /
Light / Dark). The app ships **dark-first** (a Graphite-Night-like neutral dark with the #3584e4
accent and the green keeper / red delete status pair). The design commitment:

- **"Follow the system" is the default**; light and dark switch with the desktop preference.
- **Both themes are audited** for the section 6 contrast floors — the light theme is not assumed to
  pass just because dark does (roadmap P8).
- **Status never relies on hue alone:** Keep is a check + the word "Keep"; Delete is a checked box +
  the word "Delete"; Cached is "✓ Cached"; Identical vs Similar are words.
- A dedicated **High-Contrast** pass (following the GTK high-contrast setting) is a roadmap item.

## 11. Component library

The components that cover every page; each should be drawn once with all its states before a page
mockup uses it.

| Component | Built from | States | Rules |
| --- | --- | --- | --- |
| Sidebar nav | list of rows | default, hover, active, focus, running badge | 7 items, icon + label; active uses the `-active` icon; Alt+1…9 |
| Source row | box with path + chip + meta | normal, primary, **✓ Cached**, probing | one source per row; Cached badge is read-only; tooltip = last run's metrics + drive |
| Scan ring | Cairo `RingLoader` | 0–100%, complete, faded | one per source; true files-scanned ratio; percentage centred |
| Card | `.app-card` + heading | default, attention, collapsed | one concern per card; collapsible for long tails |
| File-type / exclusion boxes | FlowBox of checkboxes + tri-state All | checked, mixed, empty | five include columns; "All" toggles a column/section |
| Group card (Results) | aligned rows via size groups | identical, similar, with keeper | name · size · path · **Keep/Delete** marker (icon + word); keeper never selectable for deletion |
| Keep/Delete marker | icon + label | keep (green check-circle + "Keep"), delete (red box + "Delete") | never colour alone |
| SpotCheck panel | drawing/preview area | image, text, PDF, office, video, loading, error | equal-width panels fill the modal; the look-first moment |
| SpaceChart | Cairo bars | before / freed | square corners, no vertical gridlines; tabular figures |
| Confirm dialog | `Adw.AlertDialog` | trash, permanent (destructive), hard-link, result | title is the question; buttons are verbs ("Move to Trash", "Keep them"); Esc cancels; file list scrolls, un-wrapped |
| Status / result toast | `Adw.Toast` | found groups, fingerprints saved | one line; "Found N groups · fingerprints saved for faster re-scans" |
| Scan-run row (History) | box | Simple / Advanced / **Stopped** chip + metrics + per-source | time, duration, throughput, files, reuse %, drive specs |
| InfoHint (i) | popover button | default, open | plain-language term/FAQ from the Knowledge glossary |

## 12. Page-by-page specifications

Every function of the current app survives; this section states each page's job and the states to
mock. (Full current behaviour is in [../FEATURES.md](../FEATURES.md).)

- **Overview (home):** a one-glance summary and the quickest path to a scan. States: first run;
  after a scan (recent result + "resume where you left off").
- **Scan:** Sources (folders/drives, with ✓ Cached badges), tier (Simple/Advanced), image toggle,
  hidden, min size, file-type filter (5 columns + All Files + Enter Extension), Exclusion
  (large-type boxes + All), Start scan top-right. States: no sources; sources with/without cache;
  scanning (per-source rings); stopped; done.
- **Results:** duplicate groups as aligned rows (name · size · path · Keep/Delete), SpaceChart,
  Delete All Duplicates / Hard-link (with the keep-rules expander), SpotCheck, Ignore. States:
  empty (no duplicates); exact groups; similar groups; a group with a changed keeper; mid-selection.
- **SpotCheck (overlay):** large side-by-side comparison for image/text/PDF/office/video before a
  destructive action. States: images; text/diff; PDF; video (playable); unsupported-with-reason.
- **Ignored:** ignored files, folders and excluded extensions, each with Resume. States: empty;
  with items.
- **History:** last cleanup (before/after bars + "You saved N GB") and **Recent scans** (performance
  per run with drive specs). States: nothing yet; cleanups only; scans only; both.
- **Settings:** theme, scan-scope presets (incl. system/recycle folders), backup policy, hash-cache
  and keep-primary toggles, default action. States: default; a preset toggled off.
- **Knowledge:** searchable glossary + FAQ. States: index; a search with results; empty search.
- **Dialogs/overlays to mock:** Move to Trash confirm; permanent-delete confirm; hard-link confirm
  (with cross-drive reason); add source / add drive; Ignore folder; SpotCheck; shortcuts overlay.

## 13. Content and voice

LinFileDedup speaks like a careful, trustworthy helper: plain words, the specific fact (with
evidence), then the one thing to do. Status and confirmation follow one three-part pattern.

**Pattern:** what happened · why (with evidence, if known) · the next step as a button or a short
instruction.

| Situation | Write | Don't write |
| --- | --- | --- |
| Identical group | "2 files are identical — same size and content, byte-verified. The newer copy is kept." | "SHA-256 match, prefix bucket collision resolved" |
| About to delete | "Move 142 copies to Trash and keep 142 originals? You can restore them from Trash." \[Move to Trash\] \[Keep them\] | "Confirm bulk unlink operation" |
| Freed | "Moved 142 files to Trash · freed 32.9 GB" \[Open Trash\] | "Operation completed: 142 files" |
| Cross-drive hard-link | "Can't hard-link across drives, so these will go to Trash instead." | "EXDEV: cross-device link" |
| Protected path | "Skipped a system location for safety — nothing there can be removed." | "Refused: path in protected set" |
| Near-duplicate | "These look alike but aren't identical. Compare them in SpotCheck before removing either." | "Perceptual hamming distance 6" |

Rules: sentence case; buttons are verbs ("Move to Trash", "Keep them", "Hard-link"). Numbers with
units ("142 files", "32.9 GB", "41.3 s"); dates relative when recent ("2 min ago"). Technical detail
lives behind InfoHint/Details, never in the headline. Name the user's object ("these files", "your
backup drive"), not the system's ("the candidate set"). Never blame the user; never use urgency
words unless something will actually be lost — **and when it will (permanent delete), say so plainly**.
One message per situation: the same fact reads the same in the row, the dialog and History.

## 14. Acceptance checklist and test plan

A screen or mockup is accepted only when it passes every item; usability tests then run on clickable
prototypes before any code change.

Per screen:

- [ ] Every interactive element is ≥ 32×32 px (WCAG floor 24); the primary action is the largest
- [ ] Text contrast ≥ 4.5:1, borders/focus ≥ 3:1, in **both** light and dark
- [ ] **Keep/Delete and every status shows an icon and a word, never colour alone**
- [ ] Focus order is sensible and drawn; focus is never hidden behind a sticky bar
- [ ] Works at the 640 px minimum window and at 200% text without horizontal scrolling
- [ ] Every control has its accessible name noted on the spec layer
- [ ] Disabled controls state why (e.g. hard-link across drives)
- [ ] No more than four visible option groups before a collapse
- [ ] Copy follows the three-part pattern (section 13)
- [ ] **Destructive actions are confirmed and named; Trash is the default; permanent delete is a
      separate, clearly-labelled choice; the keeper is never selectable for deletion; byte-verify
      runs before any group is trusted**

Usability test plan (5 participants per round, including at least one keyboard-only and one
screen-reader user):

| Task | Success means | Target |
| --- | --- | --- |
| Scan a folder and find duplicates | Groups shown without help | 5 of 5, under 30 s |
| Confirm one group is really duplicate before deleting | Opens SpotCheck, compares, then acts | 5 of 5 |
| Reclaim space from exact duplicates | Trashes extras, sees space freed | 5 of 5 |
| Keep the full-resolution photo, cull resizes | Correct keeper on first try | 4 of 5 |
| Dedup a disk against a USB backup | Adds both sources, keeps the primary copy | 4 of 5 |
| Restore a file deleted by mistake | Finds it in Trash | 5 of 5 |
| Switch to the light theme / high contrast | Finds and applies it, still readable | 5 of 5 |

Also measured: System Usability Scale (target ≥ 80) and the end-moment rating after each cleanup.
The aesthetic-usability bias is checked by running the first round on a greyscale layout.

## 15. Roadmap hooks

This reference feeds [../CONCEPT.md](../CONCEPT.md) §8. The concrete, design-driven work it defines:

- **P8 (Accessibility, responsive, both themes)** — the section 14 checklist and the section 6
  criteria: Keep/Delete as icon **and** word; contrast audit in light and dark; full keyboard flow
  for selection and SpotCheck; focus rings; 32 px target floor; 640 px / 200% reflow; screen-reader
  names and status announcements; a High-Contrast pass.
- **Voice pass** — section 13: align every status, dialog and error to the three-part pattern.
- **Component sheet** — section 11: draw each component with all states before further UI work.
- **IA review** — section 7 open question: whether Ignored + History become one "Activity" home.

## 16. Sources and caveats

- **House design reference:** *LinPrinter GUI Guide and Design Reference*
  (`MensuraMedia/linapptemplate`, `docs/design/GUI-GUIDE-AND-DESIGN-REFERENCE.md`), from which the
  ten UX laws (with evidence notes), the ten 2026 design principles, the regulatory summary, and
  the component/voice/checklist structure are carried. Legal statements in section 6 come from that
  brief and need checking before any compliance claim.
- **LinFileDedup itself:** `CLAUDE.md`, [../CONCEPT.md](../CONCEPT.md), [../FEATURES.md](../FEATURES.md),
  [../SPOTCHECK.md](../SPOTCHECK.md), the page code and the walkthrough screenshots (the audit in
  section 3), and the design pillars/safety model in CONCEPT §1 and §6.
- **Standards to read before sign-off:** WCAG 2.2, WCAG2ICT, EN 301 549, and the GNOME Human
  Interface Guidelines (for Jakob's Law alignment on the Linux desktop).

No web pages were opened while writing this; external standards are named for follow-up, not quoted.
