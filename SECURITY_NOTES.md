# FrogPaper — Security Notes & Secure Build Flow

This document explains how FrogPaper keeps API tokens and OAuth secrets out
of the packaged `.exe` / installer, and what to do if a previous build
leaked them.

**First release shipping these fixes: v1.3.2.** All builds from v1.3.2
onward (including v1.4.1+) use the secure build flow described below. Earlier builds (v1.2.0
and prior) baked the developer's real `config.json` into the EXE — see
the rotation section below if you still have users on those builds.

---

## ⚠️ IMMEDIATE ACTION REQUIRED (if you are upgrading from a leaked build)

The following secrets were found in `config.json` inside the project you
shipped previously, and were almost certainly baked into your last
`FrogPaper.exe` / `FrogPaper-Setup-*.exe` build:

| Secret | Field in `config.json` |
|---|---|
| HuggingFace API token | `huggingface_token` (starts with `hf_…`) |
| Google OAuth client ID | `google_client_id` |
| Google OAuth client secret | `google_client_secret` |

Anyone with a copy of the old `FrogPaper.exe` can extract these in seconds
(open the exe in 7-Zip, or use `pyinstxtractor`). You **must** treat them
as compromised:

1. **HuggingFace** — sign in at https://huggingface.co/settings/tokens,
   delete the leaked token, and create a new one.
2. **Google Cloud** — go to https://console.cloud.google.com/apis/credentials,
   open your OAuth 2.0 Client ID, and click **Reset client secret**. Also
   review the OAuth consent screen for any unauthorized usage.
3. **(If applicable)** Dropbox app secret and OneDrive client secret —
   rotate those too if they ever appeared in `config.json`.

After rotating, **do NOT** put the new values back into `config.json`.
Either:

- set environment variable `HUGGINGFACE_TOKEN` (the app already reads this
  first — see `utils.get_huggingface_token()`), or
- let the app store them in your OS credential manager (Windows Credential
  Manager / macOS Keychain / Linux Secret Service) via `keyring`, which
  the app already supports.

---

## What changed in this patched copy

### 1. `FrogPaper.spec`
- `config.json` has been **removed** from PyInstaller's `datas=[...]` list.
- A clean `config.template.json` has been **added** in its place. The
  template has the correct schema but every secret field is empty.

### 2. `utils.py`
- `seed_bundled_files()` now also copies the bundled `config.template.json`
  to `config.json` beside the EXE on first launch, if the user doesn't
  already have one. So end users still get a working config out of the box
  without ever receiving your real secrets.

### 3. `build_installer.bat` (Inno Setup)
- The `[Files]` section now ships `config.template.json` and renames it to
  `config.json` at install time, with `onlyifdoesntexist` so existing user
  configs are never overwritten.
- The project's local `config.json` (which may contain real dev secrets)
  is no longer shipped to end users.

### 4. `prebuild_check.py` (new)
- A pre-build gate that scans `config.json` and `config.template.json` for
  non-empty secret fields AND for suspicious patterns (`hf_…`, `GOCSPX-…`,
  `AIza…`, `ya29.`, Dropbox `sl.…`, etc.).
- Returns exit code `2` (build abort) if any secret is detected.

### 5. `build_frogpaper_exe.bat`
- Now calls `python prebuild_check.py` before running `pyinstaller`. If
  the check fails, the build is aborted with exit code `2` — no EXE is
  produced.

### 6. Project's `config.json`
- The real leaked secrets have been **scrubbed** (replaced with empty
  strings) in this working copy.

---

## How credentials flow at runtime (unchanged)

The app already had a sensible layered lookup. For example, the HuggingFace
token is resolved in this order (see `utils.get_huggingface_token()`):

1. `HUGGINGFACE_TOKEN` environment variable
2. OS credential manager via `keyring` (service `FrogPaper`, user
   `huggingface_token`)
3. `config.json` plaintext fallback (for debugging / migration only)

OAuth tokens for cloud providers follow the same pattern via
`utils.get_oauth_token()` / `utils.save_oauth_token()`. **Use #1 or #2,
not #3.** Plaintext in `config.json` is supported only so the app doesn't
break on machines without `keyring` installed; treat it as a last-resort
fallback, never as the primary store.

---

## Recommended developer workflow

1. Keep your real tokens in environment variables or in the OS
   credential manager. Never type them into `config.json`.
2. Before each release run:
   ```cmd
   build_frogpaper_exe.bat
   build_installer.bat
   ```
   The pre-build check will refuse to proceed if any secret is found in
   `config.json` or `config.template.json`.
3. Optionally, before distributing, also run a manual verification:
   ```powershell
   # Extract the EXE's bundled files and confirm no secrets are inside
   7z l dist\FrogPaper.exe | findstr /i config
   # Should show only config.template.json, never config.json
   ```

---

## Quick verification checklist

- [ ] `config.json` is listed in `.gitignore` (it is — kept for local dev only)
- [ ] `config.json` is NOT in `FrogPaper.spec` `datas=[...]` (it isn't)
- [ ] `config.json` is NOT in `build_installer.bat` `[Files]` section (it isn't — only `config.template.json`)
- [ ] `config.template.json` has all secret fields empty
- [ ] `prebuild_check.py` exits `0` before each release
- [ ] Real tokens live in env vars / `keyring`, not `config.json`
