# FrogPaper v1.7.6 — Security Release Notes

**Release date:** 2026-10-25
**Release type:** Security patch
**Severity:** High — fixes a wave of Pillow CVEs reachable from app image paths

## Summary

FrogPaper Desktop v1.7.6 is a focused security release that upgrades Pillow
from 12.3.0 to 13.0.0 and NLTK from 3.10.3 to 3.10.4. These two pins resolve
the 2026-10 Dependabot advisory wave affecting FrogPaper's image-processing
and natural-language-toolkit surfaces. No user-facing features change in this
release; the only behavior change is that the Windows EXE build process is
now reproducible from `requirements.txt` instead of relying on the developer's
ambient Python environment.

## Security advisories closed

### Pillow (was 12.3.0, now 13.0.0)

Pillow 13.0.0 patches the 2026-10 advisory wave. FrogPaper is affected
because `Image.open()` is called on:

- Every gallery thumbnail at startup (`gallery_tab.py:850-851`)
- Every image downloaded from any of the 6 AI providers
  (`wallpaper_generator.py:993-999`)
- Cloud-restored images when they enter the gallery thumbnail pass
- Style transfer filters and text overlays (`style_transfer.py`)
- Tray icon loading (`tray_manager.py:151`)
- Logo and preview images (`app.py:1100, 2051, 2069`)

The advisories closed by this upgrade include (non-exhaustive — the
Dependabot alert count will collapse from 41 to 0):

| CVE / GHSA | Title | Affected versions |
|---|---|---|
| CVE-2026-96639 / GHSA-v9pv-5gc8-w2m6 | Multi-frame loaders can reuse stale native image storage after mode transitions (alert #53) | >=11.0.0, <13.0.0 |
| CVE-2026-112403 | JPEG decoder heap buffer overflow (ImagingJpegDecode scaled output / shrinks) | <13.0.0 |
| CVE-2026-112406 | Infinite loop in PdfParser.rewrite_pages | <13.0.0 |
| GHSA-78g4-xqwv-q3g8 | Bundled libopenjp2 2.5.4 heap-buffer-overflow write reachable from Image.open().load() | >=11.1.0, <13.0.0 |
| GHSA-fc9g-5qg7-mf45 | Quadratic GIF comment copying during save | <13.0.0 |
| GHSA-654x-cwwv-5j9c | Arrow export leaks stale heap memory when PILLOW_ALIGNMENT > 1 | <13.0.0 |
| GHSA-65qm-jvmh-6pqg | GIF seek keeps rejected size after DecompressionBombError (DoS) | <13.0.0 |
| GHSA-vx6w-vv9f-6gvg | EPS load(scale) lets Ghostscript render past the decompression bomb limit | <13.0.0 |
| GHSA-xgh8-jp6q-p5x8 | ReDoS in XbmImagePlugin: 512-byte file stalls Image.open() for minutes | <13.0.0 |
| GHSA-jg86-v3jv-hrpm | Quadratic-time DoS in PDF save_all (PdfParser.next_object_id) | <13.0.0 |
| GHSA-74r2-7ff9-mjj2 | Quadratic GIF comment concatenation allows DoS in Image.open() | <13.0.0 |
| GHSA-27h8-gf7j-v5hc | NULL dereference in ImagingExpand via rank filters on zero-size images | <13.0.0 |
| GHSA-f2g6-542v-9j58 | Infinite loop in PdfParser.rewrite_pages on page tree Parent cycle | <13.0.0 |

Pillow 13.0.0 also drops support for Python 3.10 (Python 3.10 reached end of
life in October 2026). FrogPaper's declared Python minimum is now 3.11,
matching the CI matrix that already tested 3.11 and 3.12 only.

### NLTK (was 3.10.3, now 3.10.4)

NLTK 3.10.4 (released 2026-10-21) is the first NLTK release with **no known
security issues** per the Snyk advisory database. The repo's
`requirements.txt` comment previously stated "GHSA-8mgp-746c-j5xp has no
patched version yet" — that comment was correct at the time of writing but
is now stale; the comment has been removed.

The advisories closed include:

| CVE / GHSA | Title |
|---|---|
| GHSA-8mgp-746c-j5xp / CVE-2026-81726 | Model-artifact APIs bypass pathsec and touch files outside allowed roots |
| CVE-2026-79676 | Corpus readers follow symlinks outside trusted roots |

NLTK is excluded from the packaged Windows EXE via `FrogPaper.spec excludes=`
(line 25). The `nltk==3.10.4` pin matters for source/dev installs and CI.

## Build process change

`build_frogpaper_exe.bat` was rewritten to make the EXE build reproducible
from `requirements.txt` instead of relying on whatever Python packages happen
to be installed on the developer's machine. This closes the "build env differs
from the manifest" gap that allowed a vulnerable Pillow to ship in v1.7.5's EXE
even after `requirements.txt` was pinned to a specific version.

The new build script:
1. Verifies the developer's Python is 3.11+ (Pillow 13 requires it)
2. Creates a clean `.venv-build` in the repo root (reused on subsequent runs
   unless `--recreate-venv` is passed)
3. Installs `requirements.txt` into the venv with `--upgrade-pip`
4. Verifies the venv's Pillow is exactly 13.0.0 (aborts the build if not)
5. Runs the existing `prebuild_check.py` secrets check
6. Invokes PyInstaller via the venv's `python -m PyInstaller --clean FrogPaper.spec`
   so the bundled deps match `requirements.txt` exactly

To rebuild from a clean state:
```bat
build_frogpaper_exe.bat --recreate-venv
```

## requirements.txt cleanup

Consolidated duplicate entries that previously confused pip's manifest parser
(and likely contributed to Dependabot's "unknown error" when it tried to
auto-update Pillow):

| Package | Before | After |
|---|---|---|
| pillow | `Pillow>=10.0.0` + `pillow==12.3.0` | `pillow==13.0.0` |
| nltk | `nltk==3.10.3` | `nltk==3.10.4` |
| opencv-python | `opencv-python>=4.8.0,<5.0.0` + `opencv-python==4.8.1.78` | `opencv-python==4.8.1.78` |
| huggingface-hub | `huggingface_hub>=0.20.0` + `huggingface-hub==1.16.0` | `huggingface-hub==1.16.0` |
| keyring | `keyring>=24.0.0` + `keyring>=25.0.0,<26.0.0` | `keyring>=25.0.0,<26.0.0` |
| sqlalchemy | `sqlalchemy>=2.0.0` + `sqlalchemy>=2.0.0,<3.0.0` | `sqlalchemy>=2.0.0,<3.0.0` |
| pystray | `pystray>=0.19.0` + `pystray>=0.19.0,<1.0.0` | `pystray>=0.19.0,<1.0.0` |
| keyboard | `keyboard>=0.13.0` + `keyboard>=0.13.0,<1.0.0` | `keyboard>=0.13.0,<1.0.0` |

OpenCV is intentionally held at 4.8.1.78 (not bumped to 4.10+ or 4.14.0.94,
the version the previous build env reportedly used). The reason: bumping
OpenCV has historically pulled incompatible numpy 2.x wheels and forced an
ABI mismatch with the Pillow/numpy combo shipped in the EXE. Do not bump
OpenCV without testing `style_transfer.py` filters and gallery previews on
Windows first.

## Verification

### Automated (Linux sandbox — what the AI assistant could run)

- 464 unittest tests ran in 0.85s
- 403 passed, 52 skipped (optional heavy deps absent — by design, CI does
  the same)
- 1 fail + 8 errors all due to Linux env limitations (no Tk display, no
  `ctypes.windll`), NOT Pillow 13 regressions
- Pillow 13.0.0 smoke checks passed:
  - `Image.open(buf).thumbnail((240,135), Image.Resampling.LANCZOS)` ✓
  - `img.resize(size, Image.LANCZOS)` (bare constant) ✓ — works in Pillow 13
  - `from PIL import ImageSequence; ImageSequence.Iterator` importable ✓
- Full `pip install --dry-run -r requirements.txt` resolves cleanly with no
  conflicts

### Manual (Windows — what the maintainer must run)

See `windows_test_instructions.md` for the full step-by-step checklist:
1. Pull the fix branch and review the diff
2. Run unittest suite on Windows (expect `OK`)
3. Build the EXE via `build_frogpaper_exe.bat`
4. Verify Pillow 13.0.0 is bundled in the new EXE via `verify_pillow_in_exe.py`
5. Smoke-test the EXE (10 steps: startup, all gallery views, generate one
   image, tray icon, cloud restore, style transfer, text overlay, set
   wallpaper, quit)
6. Build the installer (optional)
7. Dismiss the Dependabot alerts after the v1.7.6 release tag is published

## What's not in this release

- No OpenCV upgrade (held at 4.8.1.78 deliberately; see above)
- No new features
- No theme, sound, or UI changes
- No settings schema migration (CONFIG_SCHEMA_VERSION stays at 1)
- No wallpaper format changes (PNG / JPEG / WebP outputs unchanged)
- FrogPaper Mobile is unaffected; it's a separate Android codebase

## Files changed

```
 README.md               |  25 +++--
 app.py                  |   2 +-
 build_frogpaper_exe.bat | 255 +++++++++++++++++++++++++++++++++---------------
 build_installer.bat     |   6 +-
 requirements.txt        |  94 ++++++++++++++----
 RELEASE_NOTES_v1.7.6.md | new file
 6 files changed, ~280 insertions, ~110 deletions
```

## Acknowledgements

Thanks to the previous agent (AutoClaw) for the initial repository
reconnaissance and advisory triage. The confirmed-vs-unconfirmed summary
in this release is the product of cross-checking AutoClaw's reported
findings against the upstream Pillow advisories, PyPI release metadata,
and the cloned FrogPaper repository.
