# FrogPaper — Configuration Guide

How `config.json` works, what every key does, and the three safe ways to change defaults.

---

## How the config system works

FrogPaper stores all user settings in a single JSON file, `config.json`, created automatically beside the app on first launch. On that first launch the app copies its bundled `config.template.json` to `config.json` and never touches the template again — your real config is yours from then on. The template exists so that shipped builds always start with clean, secret-free defaults (the build pipeline's `prebuild_check.py` even aborts the build if a real API token is found in either file).

The config layer is defensive by design, which makes hand-editing low-risk:

- **Schema validation on every load** — each known key is type-checked. A wrong-typed value (e.g. an int where a string belongs) is dropped with a log warning and the app falls back to its default instead of crashing. Hand-edited integral floats like `"30.0"` are coerced to `30`.
- **Unknown keys are preserved** — keys the app doesn't recognize are kept untouched, so custom or future keys survive round-trips.
- **Corruption recovery** — if `config.json` can't be parsed, it is backed up as `config.json.corrupt` and the app starts fresh. Nothing is silently lost.
- **Version stamping** — every save stamps `config_version`, and a rename registry exists so future key renames upgrade older configs transparently.

## Three ways to change settings

| Method | When to use | How |
|---|---|---|
| **Settings tab (recommended)** | Everyday changes | Open Settings in the app and edit. Values are validated and saved atomically. |
| **Hand-edit `config.json`** | Bulk tweaks, restoring a known state | **Close the app first.** The app writes config on exit and during use; editing while it runs means your changes get overwritten. Edit, save, relaunch. |
| **Edit `config.template.json`** | Changing *first-run defaults* for a build or redistribution | Edit the template, keep all credential fields empty, rebuild. Fresh installs seed from it; existing users' configs are never overwritten. |

---

## Preference keys (safe to edit)

These are the settings the Settings tab exposes. Types matter — the schema enforces them.

| Key | Type | Ships as | Allowed values / notes |
|---|---|---|---|
| `app_theme` | str | `"neoncyber_light"` | Theme id — see the theme id list below |
| `dimensions` | str | `"1920x1080"` | `WIDTHxHEIGHT`. Presets: `1920x1080` (16:9), `1080x1920` (portrait), `1024x1024` (square); custom sizes allowed |
| `provider` | str | `"Pollinations.ai (Free - No Key)"` | Must match one of the 6 exact provider strings (see below) — safest changed via the UI |
| `model_id` | str | `"flux"` | Provider-specific model id (see below) — safest changed via the UI |
| `wallpaper_format` | str | `"PNG"` | `PNG`, `JPEG`, `WebP` |
| `wallpaper_quality` | str | `"Low"` | `Maximum`, `High`, `Medium`, `Low` — lower = smaller files, minimal visual difference at desktop size |
| `slideshow_enabled` | bool | `true` | Master switch for wallpaper rotation |
| `slideshow_interval` | int | `1` | **Minutes**, valid range 1–60 (UI slider). ⚠ The template ships `1`; the Settings UI default is `60` |
| `slideshow_source` | str | `"all"` | `all`, `generated`, `manual`, `favorites`, `styled` |
| `slideshow_order` | str | `"random"` | `random`, `newest`, `oldest` |
| `slideshow_skip_duplicates` | bool | `true` | No repeat until every image has been shown |
| `slideshow_pause_on_fullscreen` | bool | `true` | Don't rotate while a fullscreen app (game/video) is detected |
| `minimize_to_tray` | bool | `true` | Minimize to system tray instead of the taskbar |
| `remember_settings` | bool | `false` | When ON, prompt fields (subject, lighting, mood, …) persist across launches; when OFF, everything resets to starter defaults and saved values are wiped |
| `auto_generate_on_startup` | bool | `false` | Generate a fresh random wallpaper at each launch; while ON, remembered settings are **not** restored on startup |
| `startup_subject` | str | `"frog"` | Subject used for the startup auto-generation |
| `auto_backup_enabled` | bool | `true` | Daily cloud backup |
| `auto_backup_hour` | int | `11` | Hour of day, 0–23 |
| `auto_backup_minute` | int | `15` | Minute of hour, 0–59 |
| `sync_scope` | str | `"everything"` | `everything` (all wallpapers) or `favorites` (favorites only) |

### Theme ids for `app_theme`

| Family | Dark | Light |
|---|---|---|
| Forest Green | `darkforest` | `lightforest` |
| Frog Swamp | `frogswamp` | `frogswamp_light` |
| Ocean Blue | `oceanbluenew` | `lightocean` |
| Dark Glass | `darkglass` | `darkglass_light` |
| Sunset Ember | `darksunset` | `lightsunset` |
| Warm Paper | `warmpaper_dark` | `warmpaper` |
| Neon Cyber | `neoncyber` | `neoncyber_light` |
| High Contrast | `darkcontrast` | `lightcontrast` |
| Studio Neutral | `studioneutral` | `studioneutral_light` |

### Providers and model ids

The `provider` string is matched exactly, so prefer the UI dropdown. The six valid values, and the `model_id` values each accepts:

| Provider string | Model ids (`model_id`) |
|---|---|
| `Pollinations.ai (Free - No Key)` | `flux`, `flux-realism`, `flux-anime`, `flux-3d`, `flux-cablyai`, `turbo` |
| `Cloudflare Workers AI (Free Tier)` | `@cf/black-forest-labs/flux-1-schnell` |
| `Hugging Face Inference` | `black-forest-labs/FLUX.1-schnell`, `black-forest-labs/FLUX.1-dev`, or a custom id |
| `Prodia (Pro Account)` | FLUX.schnell / FLUX.dev / FLUX.1-fill / SDXL variants — pick via UI |
| `Replicate (Pay-Per-Image)` | pick via UI |
| `Fal.ai (Fast Inference)` | pick via UI |

---

## App-managed keys (leave these alone)

The app writes these automatically. Editing them by hand is harmless but pointless — they're session state, favorites, and bookkeeping, and they'll be overwritten the next time you use the app.

| Key | Purpose |
|---|---|
| `first_run_completed` | Marks that the first-launch flow has run |
| `last_style`, `last_setting`, `last_lighting`, `last_mood`, `last_color`, `last_atmosphere` | Remembered prompt fields (written when *Remember settings* is ON) |
| `last_neg_preset_selections` | Which negative-preset checkboxes were ticked (map of 6 booleans) |
| `last_neg_custom_terms` | Remembered custom negative terms |
| `completed_tutorials` | Which tutorial popups you've dismissed |
| `skipped_update_version` | Update version you chose to skip |
| `auto_backup_last_run` | Timestamp of the last cloud backup |
| `pinned_options` | Your ★ pinned dropdown values, per category (`subject`, `setting`, `lighting`, `mood`, `atmosphere`, `color_family`, `color_variation`) |
| `oauth_tokens` | Cloud-provider OAuth fallback storage (the OS credential manager is preferred) |
| `config_version` | Schema version stamp — managed by the app |

## Credential keys (set via Settings, never ship them)

| Key | Used for |
|---|---|
| `huggingface_token` | Hugging Face Inference |
| `cloudflare_token`, `cloudflare_account_id` | Cloudflare Workers AI |
| `prodia_key` | Prodia |
| `replicate_token` | Replicate |
| `fal_key` | Fal.ai |
| `dropbox_app_key`, `dropbox_app_secret` | Dropbox sync |
| `onedrive_client_id`, `onedrive_client_secret` | OneDrive sync |
| `google_client_id`, `google_client_secret` | Google Drive sync |

Notes on credentials:

- You never need to edit these by hand — enter them in **Settings → Cloud** or **Settings → Generation**, and the app stores them.
- For Hugging Face, resolution order is: `HUGGINGFACE_TOKEN` environment variable → OS credential manager (keyring) → `config.json`. The environment variable is the safest option on a shared machine.
- Keep all credential fields **empty** in `config.template.json`. The pre-build secret check refuses to produce an EXE if a real token is present.
