# FrogPaper Cloud Restore — Analysis & Implementation Plan

**Status:** proposal, not implemented
**Target:** v1.8 (or as its own release)
**Goal:** after a reinstall, disk failure, or new PC, a user can pull their entire wallpaper
collection (and the metadata that makes it usable) back out of Google Drive / OneDrive / Dropbox
into a fresh FrogPaper install — without ever risking local files.

---

## 1. What exists today

### 1.1 Cloud layer

| Piece | File | What it actually does |
|---|---|---|
| OAuth + file APIs | `cloud_providers.py` | `GoogleDriveProvider`, `OneDriveProvider`, `DropboxProvider`, each with `authenticate()`, `upload_file()`, `list_files()`, `download_file()`. Factory `get_provider()` at line 953. |
| Sync engine | `sync_manager.py` | Local-change detection → **upload only**. `perform_sync()` scans `wallpapers/{generated,manual,favorites,styled}`, hashes each image, uploads new/changed files, and rebuilds `sync_metadata.json`. |
| UI / scheduling | `app_cloud_mixin.py` | Cloud account cards, `_manual_sync()` (main-thread pre-auth, background upload), daily backup scheduler (`auto_backup_hour` / `auto_backup_minute`, catch-up on launch). |
| Storage layout in cloud | providers | `FrogPaper/` root with subfolders `Generated`, `Manual`, `Favorites`, `Styled`; uploads are matched by filename and overwritten in place. |
| UI surface | `settings_categories.py` `_build_cloud_category()` (≈line 450), `settings_components.CloudProviderCard` | Connect cards, "Sync Now", scope radio buttons, backup time, last-backup label. |

Auth material lives in the OS keyring via `utils.get_oauth_token()` / `save_oauth_token()`
(`config.json` fallback). Scopes: Google `drive.file` + `drive.metadata.readonly`,
OneDrive `Files.ReadWrite`, Dropbox offline token.

### 1.2 Metadata that a restore must also bring back

- **Tags** — SQLite `image_tags` table (`database.py`), keyed by **absolute, resolved file path**
  (`gallery_manager.add_tags_to_image()` does `str(Path(image_path).resolve())`). Same for
  `prompt_params`.
- **Favorites** — actual copies under `wallpapers/favorites/` (so the file tree alone carries them).
- **Prompt params per image**, sessions, recipes, presets, prompt library — SQLite / JSON.
- **Config** — theme, provider, dimensions, format, slideshow source/order, pinned dropdowns.

None of that is backed up today. A restore would return images with zero tags and a **broken tag
index**, because tag rows point at the old absolute paths.

### 1.3 Verified gaps that block a restore today

1. **No inbound sync at all.** `perform_sync()` never enumerates remote files. `sync_metadata.json`
   has no remote IDs, only local hashes, so it cannot map a remote object back to a local path.
2. **`list_files()` cannot find the backup.** Google/OneDrive need a `folder_id`; without one they
   list *My Drive root* / *OneDrive root*. Dropbox defaults to `""` = Dropbox root, not `/FrogPaper`.
   None of them walk subfolders, none paginate (Drive 100-item default, Graph `@odata.nextLink`,
   Dropbox `has_more`/cursor), so even a manual restore would see a fraction of a real collection.
3. **`download_file()` is not crash-safe.** Google writes chunks straight into the destination;
   OneDrive does `response.content` (whole file in RAM, no timeout); Dropbox resolves by id. An
   interrupted download leaves a truncated `.png` that the gallery happily shows.
4. **No retries / no timeouts.** A single 429 from Drive or a stalled Graph request aborts a restore
   (some `requests.get` calls in `cloud_providers.py` have no `timeout=` at all).
5. **Deletion is a stub.** `sync_manager._delete_remote_file()` is literally `pass` with a
   "placeholder" comment. Local deletions never propagate; the metadata entry is then dropped by
   `_update_sync_metadata()`, so the app forgets the file exists remotely. After a restore those
   deleted images come back — a resurrection bug.
6. **Every manual sync wipes the index.** `app_cloud_mixin._manual_sync()` sets
   `sync_metadata = {"files": {}, "last_sync": None}` before syncing, which forces a full re-upload
   every time and throws away anything a restore would need to reconcile.
7. **No conflict model.** `_resolve_conflict()` always returns the local file, in both manual and
   automatic mode. There is no "remote is newer" concept.
8. **`file_watcher.py` is dead code.** Nothing instantiates `FileWatcher`, yet the README (v1.2.0
   notes) and the built-in tutorial ("Changes are detected automatically and synced in the
   background") promise real-time auto-sync. Actual triggers: the Sync button and the daily scheduler.
9. **No disk-space check, no dry run, no progress-per-file UI** for inbound work.
10. **`sync_metadata.json` is committed to git** (tracked, empty) even though it is machine-local
    state containing local relative paths and hashes. `.gitignore` does not cover it.

### 1.4 The one real-world risk nobody can code around

Auth to the cloud requires the **app's own OAuth client credentials** (Google client ID/secret,
Dropbox app key/secret, OneDrive client ID). Those are deliberately not shipped in the build
(`prebuild_check.py`, `SECURITY_NOTES.md`) and are not recoverable from the cloud. If the user loses
them *and* creates a new Google Cloud project, the new client **cannot see files uploaded by the old
one** — `drive.file` is per-app access. Two mitigations, both cheap and both in this plan:

- a text **Recovery Kit** export (non-secret: which providers, folder name, scopes, manifest
  timestamp) so a user knows what to re-create, and
- **Restore from a local folder** — point FrogPaper at a Google Drive / OneDrive / Dropbox *desktop
  sync folder* and restore from disk. This works with no OAuth at all and is the ultimate safety net.

---

## 2. Design principles

1. **Restore never destroys.** Default behaviour writes only files that are missing locally. No
   overwrite, no delete, no rename of an existing file — ever — unless the user explicitly opts in.
2. **Preview before write.** Restore is a two-step flow: build a plan → show counts and a scrollable
   list → user confirms → execute. The plan is a pure function of the remote catalog + local disk
   (testable without network).
3. **Verify every byte.** Download to `<name>.part`, check size + SHA-256, then `os.replace()`.
   A failed or cancelled download leaves no file behind.
4. **Idempotent and resumable.** Running restore twice is safe; already-restored files are skipped by
   hash. Cancelling mid-run and re-running continues where it stopped.
5. **Portable metadata.** Tags/prompt params travel as *relative* paths and are re-keyed to the new
   install's absolute paths. Never copy raw tag rows across machines.
6. **Cloud layout stays backward compatible.** Existing `FrogPaper/{Generated,Manual,Favorites,Styled}`
   folders keep working for users who already uploaded with v1.2–v1.7. The new manifest is additive.

---

## 3. Proposed architecture

```
                    ┌──────────────────────────────┐
   upload path      │  sync_manager.perform_sync() │
   (existing)       └──────────────┬───────────────┘
                                   │ after N uploads
                                   ▼
                    ┌──────────────────────────────┐
                    │  backup_manifest.build()     │  sha256 + tags + prompt params
                    │  upload to FrogPaper/        │  + safe config subset
                    │    backup-manifest.json      │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
   restore path     │  cloud_restore.RemoteCatalog │  recursive, paginated, normalized
                    │  (Drive / OneDrive / Dropbox)│  RemoteFile records + manifest
                    │  or LocalFolderSource        │  (drive-sync folder, no OAuth)
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  RestorePlan (dry run)       │  MISSING / IDENTICAL /
                    │  shown in a preview dialog   │  CONFLICT / INVALID / NO_SPACE
                    └──────────────┬───────────────┘
                                   ▼ user confirms
                    ┌──────────────────────────────┐
                    │  RestoreExecutor             │  .part → verify → os.replace
                    │  progress + cancel           │  collision-safe names
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  MetadataImporter            │  tags/prompt params re-keyed,
                    │  (tags, prompt params,       │  merged (union) with existing,
                    │   optional sessions/presets) │  never overwrites
                    └──────────────┬───────────────┘
                                   ▼
                       gallery.load_gallery() + refresh views,
                       restore_log_<ts>.json written
```

**New modules**

- `cloud_restore.py` — one cohesive home for "read the backup back": remote catalog abstraction,
  manifest parsing, planning, download execution, metadata import. (~450–600 lines)
- `recovery_kit.py` (optional, Phase 5) — plain-text recovery info export.

**Touched modules:** `cloud_providers.py`, `sync_manager.py`, `app_cloud_mixin.py`,
`settings_categories.py`, `settings_components.py`, `tray_manager.py`, `utils.py`,
`config.template.json`, `CONFIG_GUIDE.md`, `README.md`, `tutorial_manager.py`, `.gitignore`,
`tests/test_cloud_restore.py` (new).

---

## 4. Data contracts

### 4.1 Normalized remote file

Every source (three providers + local folder) yields the same shape, so planning code never
branches on provider:

```python
@dataclass(frozen=True)
class RemoteFile:
    provider: str          # "google_drive" | "onedrive" | "dropbox" | "local_folder"
    file_id: str           # provider id, or absolute path for local_folder
    name: str              # "2026-10-19_14-03-22_frog.png"
    subfolder: str         # "generated" | "manual" | "favorites" | "styled" | ""
    rel_path: str          # "wallpapers/generated/<name>"  ← manifest override wins
    size: int
    modified: str          # ISO-8601
    sha256: str | None     # from manifest, else None
```

### 4.2 `FrogPaper/backup-manifest.json` (new, additive)

```json
{
  "schema": 1,
  "app_version": "1.8.0",
  "created": "2026-10-19T14:03:22",
  "device_id": "9f2c…",
  "image_count": 1482,
  "images": [
    {
      "rel_path": "wallpapers/generated/2026-10-19_14-03-22_frog.png",
      "subfolder": "generated",
      "size": 2413821,
      "sha256": "6b1f…",
      "modified": "2026-10-19T14:03:22",
      "favorite": false,
      "tags": ["frog", "neon"],
      "prompt_params": {"subject": "frog", "mode": "Cinematic"}
    }
  ],
  "library": {
    "sessions": [], "recipes": [], "presets": [], "prompt_library": []
  },
  "config_safe": {
    "app_theme": "darkforest", "dimensions": "1920x1080",
    "wallpaper_format": "PNG", "slideshow_source": "generated",
    "slideshow_interval": 60, "pinned_options": {}
  }
}
```

Rules:
- **No secrets, ever** — no tokens, no client IDs/secrets, no credentials. `prebuild_check.py` stays
  untouched; add a unit test asserting the manifest builder strips every `*_token` / `*_key` /
  `*_secret` / `oauth_tokens` key.
- The library block is optional and only filled when the user enabled "back up settings & library".
- Cap: if the manifest exceeds ~8 MB (≈25k images), split into `backup-manifest-1.json`, `-2.json`
  and record `"part": 1, "parts": 3`. Keep it simple: JSON, not gzip, so a user can read it in a
  text editor years from now.
- Upload through a new provider method `upload_bytes(name, data, subfolder="")` so the manifest never
  has to be written into the user's wallpaper folders.

### 4.3 `sync_metadata.json` v2

```json
{
  "version": 2,
  "last_sync": "2026-10-19T14:03:40",
  "manifest_uploaded": "2026-10-19T14:03:41",
  "files": {
    "wallpapers/generated/a.png": {
      "hash": "sha256…", "size": 2413821,
      "modified": "2026-10-19T14:03:22",
      "remote": {
        "google_drive": {"id": "1AbC…", "path": null, "uploaded": "…"},
        "dropbox":      {"id": "id:xyz", "path": "/FrogPaper/Generated/a.png"}
      },
      "synced_at": "2026-10-19T14:03:41"
    }
  }
}
```

- v1 files load unchanged (`_load_sync_metadata` returns them as-is), and gain a `remote` block on
  their next successful upload. No destructive migration.
- Remote IDs unlock real deletion and let restore correlate a remote object to the exact local file
  even if the user renamed something locally.
- Add `sync_metadata.json` to `.gitignore` and `git rm --cached` the tracked empty copy.

---

## 5. Implementation plan (six PR-sized phases)

### Phase 0 — Provider hardening (no user-visible feature)

**Files:** `cloud_providers.py`

1. Add `_request_with_retry(fn, *, attempts=4, base=1.0)` helper: retries on 429/500/502/503/504,
   honours `Retry-After`, exponential backoff + jitter, logs the final failure. Use it for every
   Drive/Graph/Dropbox call.
2. Add explicit `timeout=` to every `requests` call (connect 10 s, read 120 s).
3. Add `list_tree(root_name="FrogPaper")` to each provider, returning `RemoteFile` dicts:
   - Drive: resolve/create the `FrogPaper` folder (read-only path: resolve only, never create during
     restore), list children with `q="'<id>' in parents and trashed=false"`, then recurse into the
     four known subfolders, following `nextPageToken`.
   - OneDrive: `GET /me/drive/root:/FrogPaper:/children?$expand=…` then per-subfolder children,
     following `@odata.nextLink`.
   - Dropbox: `files_list_folder("/FrogPaper", recursive=True)` with `has_more`/cursor loop; derive
     `subfolder` from `path_display`.
   - Filter to `{.png,.jpg,.jpeg,.webp,.bmp}`; ignore anything else (notably the manifest).
4. Make `download_file()` atomic: stream to `dest.with_suffix(dest.suffix + ".part")`, `flush` +
   `os.fsync`, then `os.replace`. Return `(ok, bytes_written)` or raise a typed
   `CloudDownloadError` so callers can distinguish "not found" from "network died".
5. Implement `delete_file(file_id)` for all three (`files().delete`, `DELETE /me/drive/items/{id}`,
   `files_delete_v2`). Required by Phase 1 so deletions stop resurrecting.
6. `upload_bytes(name, data, subfolder="")` for small JSON payloads.

**Acceptance**
- `list_tree()` on a fixture-backed fake HTTP layer returns all 4 subfolders, >100 Drive files
  (pagination), and Dropbox `has_more`.
- A forced 429 then 200 is retried and succeeds; a 403 fails fast without retry storms.
- Interrupting `download_file()` leaves no destination file and no `.part` after cleanup.
- `ruff check .` clean (CI lint gate).

---

### Phase 1 — Cloud-side backup manifest + honest deletion

**Files:** `sync_manager.py`, new `cloud_restore.py` (manifest half), `cloud_providers.py`

1. `cloud_restore.build_manifest(app_dir)`:
   - Walk the four wallpaper dirs, compute SHA-256 (reuse `SyncManager._compute_file_hash`).
   - Pull tags + prompt params from `gallery_manager.load_tags()` (already merges DB and JSON
     fallback) — **not** raw SQL, so the JSON fallback path keeps working.
   - Pull optional library blocks from `session_manager` / `preset_manager` / `template_system` only
     when `backup_include_library` is on.
   - Build `config_safe` from an explicit allow-list (never `CONFIG_SCHEMA` filtered by suffix —
     allow-list is safer and self-documenting).
2. `SyncManager.perform_sync()`: after a successful pass, if `cloud_manifest_enabled`, build and
   upload the manifest to each provider's `FrogPaper/` root; record `manifest_uploaded`.
   Failures are non-fatal (log + `results["manifest_error"]`).
3. Store per-provider remote IDs in `sync_metadata` v2 (Phase 0 returns them).
4. Implement `_delete_remote_file()` for real: look up `remote[provider].id`, `HEAD`/metadata the
   object, delete only if the remote size/hash still matches what we uploaded. If it differs, leave
   it and log "remote modified elsewhere — not deleting".
5. Stop wiping `sync_metadata` in `_manual_sync()`. Replace with `force_full_upload=True` passed
   through `perform_sync()` — same behaviour, but the previous index survives a failed sync.
6. Migration: on load, if `version != 2`, keep the file, add `version: 2`, and continue.

**Acceptance**
- After a sync, `FrogPaper/backup-manifest.json` exists on every connected provider, validates
  against the schema, lists every image with a matching sha256 and its tags.
- Deleting an image locally, then syncing, removes it remotely **and** leaves no metadata entry.
- A remote file modified by hand (different size) is *not* deleted.
- Manifest contains no value matching any secret key or token-shaped string
  (`hf_…`, `sl.…`, `GOCSPX-…`, `ya29.`, `AIza…`).
- Existing v1 `sync_metadata.json` from a v1.7 install loads and upgrades without losing entries.

---

### Phase 2 — Restore engine (the core)

**Files:** new `cloud_restore.py` (rest of it), `sync_manager.py` (small hooks)

1. `RemoteCatalog.load(providers)` → merged `RemoteFile` list.
   - With a manifest: manifest entries win for `rel_path`/`sha256`/tags; remote files not in the
     manifest are added with `rel_path` inferred from their subfolder.
   - Without a manifest (v1.7-era backups): derive `rel_path` from `subfolder + name`. This fallback
     is mandatory — it is what makes the feature useful on day one.
   - Same file present on two providers: keep both as candidates; dedupe identical `sha256` (or
     identical `size`+`name` when no hash) and remember the second provider as a redundant source.
2. `RestorePlan.build(catalog, app_dir, options)` — pure, no I/O beyond `stat`/`sha256`:
   - `IDENTICAL` — local file exists with same size + hash → skip.
   - `MISSING` — no local file → will download.
   - `CONFLICT` — local file exists, content differs → depends on
     `restore_conflict_policy`: `keep_both` (default, download as `name (restored YYYY-MM-DD).ext`),
     `skip`, or `overwrite` (explicit opt-in only).
   - `INVALID` — bad extension, path traversal (`..`), Windows-reserved name, name > 200 chars.
   - `NO_SPACE` — flagged at plan level after `shutil.disk_usage(app_dir)` vs sum of download sizes
     (with a 10 % headroom).
   - Duplicate remote paths (`a.png` twice) get deterministic suffixed names.
3. `RestoreExecutor.run(plan, progress_cb, cancel_event)`:
   - Serial (or 2 workers; providers rate-limit hard) downloads via the provider that owns the file,
     with automatic fallback to a second provider if one fails.
   - `.part` → size check → sha256 check (when known) → `os.replace`.
   - Per-file retry once on network error, then record in `failed[]` and continue.
   - Writes `wallpapers/<subfolder>/` as needed; never touches an existing path.
4. `MetadataImporter.import_(manifest, plan, app_dir, options)`:
   - Map `manifest.rel_path` → **actual** local path used (including `(restored …)` names).
   - Tags: union-merge with existing rows (`add_tags_to_image`), never remove, skip if metadata off.
   - Prompt params: only set when no local params exist for that path.
   - Library blocks: merge-by-name, skip existing names, never overwrite.
   - `config_safe`: only apply keys the user did not already customize (or apply all with an explicit
     checkbox, default off).
   - Rebuild the tag cache (`gallery_manager._invalidate_tags_cache`) and drop tag rows whose file no
     longer exists (`cleanup_orphaned_tags`) *after* remapping.
5. Safety rails:
   - `SyncManager.restore_in_progress` flag; `perform_sync()` returns `{"status": "busy"}` and the
     daily scheduler skips while it is set.
   - Suppress the file watcher (when it eventually gets wired up) and suppress manifest upload for
     the duration, so a restore can never trigger a re-upload storm.
   - Restore writes a `restore_log_<timestamp>.json` (plan + outcomes + errors) next to the app, so
     a "where did my 12 images go?" question is answerable.
6. `LocalFolderSource` (same interface): restore from any directory the user picks — a Drive/Dropbox
   desktop-sync folder, an SD card, or an old backup drive. No OAuth, no API. This is the escape
   hatch when credentials are lost, and it reuses the planner/executor unchanged.

**Acceptance**
- Dry run performs **zero** writes (asserted by snapshotting the tree).
- Plan on a fresh install against a 3-provider catalog lists all 4 subfolders and correctly counts
  identical vs missing vs conflicting.
- Default conflict policy leaves every pre-existing local byte untouched.
- Killing the process mid-download leaves no truncated image; re-running completes the rest.
- Restoring twice yields the same tree (no duplicates) and no duplicated tag rows.
- Tags land on the restored absolute paths and are visible in the Gallery tag dropdown.
- No `.part` files remain after success, failure, or cancellation.
- Restore of a v1.7-era backup (no manifest) restores images into the right folders (untagged, as
  expected) and logs that no manifest was found.

---

### Phase 3 — UI

**Files:** `settings_categories.py`, `settings_components.py`, `app_cloud_mixin.py`, `app.py`,
`tray_manager.py`

1. New "Restore & Recovery" `SettingCard` under **Settings → Cloud & Backup**, below Sync Settings:
   - `Preview restore…` (primary) → plan dialog: per-provider source, N to download / N identical /
     N conflicts / total size / free space, scrollable list with status icons.
   - `Restore from folder…` (secondary) → folder picker → same preview dialog with `local_folder`.
   - Checkboxes: `Include tags & library metadata` (default on), `Overwrite existing files`
     (default off, with a warning line when ticked), conflict policy combo
     (`Keep both` default / `Skip` / `Overwrite`).
   - Progress: determinate bar + "12 / 1482 · 3.1 MB/s" + Cancel, reusing the status bar and
     `run_background` / `schedule_ui_update` from `app_runtime`.
   - Result dialog: written / skipped / conflicts / failed, with `Open wallpaper folder` and
     `Open restore log`.
2. Add `Restore from Cloud…` to the tray menu, right after the sync items
   (`tray_manager.py`, plus `_tray_restore_from_cloud` in `app_cloud_mixin`).
3. First-run nudge: if the gallery is empty **and** a cloud token exists, show a one-line, dismissible
   banner in the gallery panel ("Cloud backup found — Restore from Cloud") rather than a modal.
   Store dismissal in config so it never nags.
4. Main-thread discipline: authentication and all dialogs on the main thread (same pattern as
   `_manual_sync`), downloads in background, `schedule_ui_update` for every widget touch.

**Acceptance**
- Buttons are reachable by keyboard, styled by the theme engine, and re-theme live (the existing
  theme engine already re-themes cloud cards — add the new refs there).
- Cancel stops within one file, reports partial results, and leaves a clean tree.
- The plan dialog scrolls with the mouse wheel like the rest of Settings (v1.6 regression class).
- Tray action restores the window and opens the same dialog.

---

### Phase 4 — Config, docs, and repo hygiene

**Files:** `utils.py`, `config.template.json`, `CONFIG_GUIDE.md`, `README.md`,
`tutorial_manager.py`, `.gitignore`, `SECURITY_NOTES.md`, `FrogPaper.spec`/`build_installer.bat`
(file lists only if new modules need adding)

New config keys (add to `CONFIG_SCHEMA`, template, and guide):

| Key | Type | Default | Meaning |
|---|---|---|---|
| `cloud_manifest_enabled` | bool | `true` | Upload `backup-manifest.json` after each sync |
| `backup_include_library` | bool | `true` | Include sessions/recipes/presets in the manifest |
| `restore_include_metadata` | bool | `true` | Import tags/prompt params on restore |
| `restore_conflict_policy` | str | `"keep_both"` | `keep_both` / `skip` / `overwrite` |
| `restore_overwrite_existing` | bool | `false` | Allow overwriting differing local files |
| `restore_last_run` | str | `""` | ISO timestamp of the last completed restore |
| `restore_nudge_dismissed` | bool | `false` | Hide the empty-gallery restore hint |

Docs:
- README: replace the v1.2.0 "Automatic Sync / real-time monitoring" claim with what actually ships;
  add a **Restore after a reinstall** section with the credential caveat.
- Tutorial "Cloud Sync": same correction + a restore walkthrough.
- `CONFIG_GUIDE.md`: new keys, and a clear note that tags are stored by absolute path.
- `.gitignore`: add `sync_metadata.json`, `restore_log_*.json`, `*.part`; `git rm --cached
  sync_metadata.json`.
- `SECURITY_NOTES.md`: state that the manifest is metadata only, never credentials, and that the
  recovery kit contains no secrets.

**Acceptance**
- A fresh install with a default config and a fake provider runs a restore end-to-end.
- Unknown/old config files still load (`_validate_config` drops nothing new).
- `ruff check .` and `python -m unittest discover -s tests -v` green (Windows CI).

---

### Phase 5 (optional, recommended) — Recovery kit + "backup health"

**Files:** new `recovery_kit.py`, `settings_categories.py`, `app_cloud_mixin.py`

- **Recovery Kit** (plain text / JSON, user-saved): which providers were used, the folder name,
  scopes, last successful sync + manifest timestamp, app version, config schema version — explicitly
  **no secrets**. Tells a future user exactly what to recreate.
- **Backup health** line in the Cloud card: "Last backup 2 h ago · 1 482 images · manifest ok" or a
  warning ("connected, but no successful backup in 14 days", "manifest missing — restore will be
  images-only"). Cheap, and it turns a silent failure into something a user notices before they need
  the backup.
- Optional scheduled **restore verification**: on demand, download a random sample of 3 images,
  verify hashes, discard — proves the backup is readable without a full restore.

---

## 6. Test plan

All tests are `unittest`, no network, no real cloud — a `FakeProvider` implementing the Phase 0
interface plus `tmp_path` app dirs. Add `tests/test_cloud_restore.py`.

| # | Test | Guards |
|---|---|---|
| 1 | Plan classifies MISSING / IDENTICAL / CONFLICT correctly | planning core |
| 2 | Conflict `keep_both` writes `name (restored …).png`, original untouched | non-destructive promise |
| 3 | `overwrite` only when explicitly enabled | accidental data loss |
| 4 | Truncated download is rejected and no file remains | byte verification |
| 5 | Cancellation mid-plan/mid-download leaves no `.part` | crash safety |
| 6 | Re-run is idempotent (no duplicates, no duplicate tags) | resumability |
| 7 | Tag path remapping from an old absolute base to a new one | portability |
| 8 | No-manifest backup restores into correct subfolders | v1.7 compatibility |
| 9 | Pagination: 250 fake remote files all appear in the catalog | `list_files` truncation bug |
| 10 | Two providers, same content → downloaded once | dedupe |
| 11 | Manifest contains no secret-shaped keys/values | credential leak |
| 12 | `perform_sync()` returns `busy` while restore runs | upload/restore race |
| 13 | Deletion only removes remote when size/hash still match | resurrection fix |
| 14 | v1 `sync_metadata.json` upgrades to v2 without losing entries | migration |
| 15 | Invalid remote names (`..`, `CON`, 300 chars) are rejected, not written | path traversal |
| 16 | Insufficient disk space aborts before any write | graceful failure |

Manual/integration checklist (documented in the PR, run against a throwaway Google Drive folder):
connect → sync 5 images → verify manifest → delete local `AppData` copy entirely → reinstall →
reconnect → preview restore → restore → confirm images, tags, favorites, gallery views, slideshow,
and a follow-up sync that produces no duplicate uploads. Also test OneDrive and Dropbox, the
local-folder source, and a cancelled restore resumed later.

---

## 7. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| User loses OAuth client credentials; new Google client cannot see old `drive.file` uploads | restore impossible via API | Recovery Kit + **Restore from local sync folder**; document that client credentials are the key |
| Google `drive.file` vs broader scope | can't read files uploaded by a different client | keep `drive.file`; do not request `drive.readonly` (verification burden) |
| Rate limits on large collections (thousands of files) | slow, 429s | backoff + jitter, 2 workers max, resumable, per-file failures don't abort the run |
| Manifest grows with collection | multi-MB upload daily | part files, skip re-upload when the manifest hash is unchanged |
| Tag rows keyed by absolute path | tags detached on restore | manifest stores relative paths; remap on import; never copy raw DB rows |
| Restore triggers auto-backup / watcher loops | upload storm, double files | `restore_in_progress` flag, suppressed manifest upload, future watcher guard |
| Partial writes | corrupt gallery images | `.part` + fsync + `os.replace` + hash verify |
| Restore quietly overwrites something | data loss | plan preview, `keep_both` default, overwrite requires explicit checkbox |
| Dropbox/OneDrive token expiry mid-restore | half-finished run | re-auth before starting, refresh on 401 once, resume is safe |
| Manifest schema drift over years | unreadable backup | `schema` field, ignore-unknown-fields reader, never reject a manifest for extra keys |

---

## 8. Out of scope (deliberately)

- Two-way continuous sync with automatic conflict merging between machines. This plan restores
  *into* a machine; turning sync into a true multi-device merge is a bigger design (vector clocks /
  per-device journals) and should be a separate proposal.
- Encrypting cloud backups. Nice-to-have, but it makes the "recover without FrogPaper" story worse
  (a plain `FrogPaper/` folder works even if the app dies). Revisit with a user-chosen passphrase and
  documented recovery key.
- Migrating to a server-side account model. Pollinations-style, no server, stays a feature.

---

## 9. Suggested sequencing

1. **Phase 0 + 1** (hardening + manifest) — ships quietly, makes every future restore possible and
   fixes the deletion-resurrection bug. Low risk.
2. **Phase 2** (engine + tests) — the bulk of the work; no UI yet, fully testable headless.
3. **Phase 3** (UI) — thin layer over a tested engine.
4. **Phase 4** (docs/config/hygiene) — before release, not after.
5. **Phase 5** (recovery kit, backup health) — same release if time allows, otherwise v1.8.1.

Estimated size: Phases 0–4 ≈ 1 200–1 500 new lines plus ~250 lines of edits; tests ≈ 500–700 lines.
