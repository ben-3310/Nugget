# Deployment TODO

## Context
- `RELEASING.md` and `.github/workflows/build.yml` now orchestrate macOS signing/notarization, Windows/Linux packaging, and release publishing with `softprops/action-gh-release`.
- `compile.py` reads `NUGGET_CODESIGN_HASH` before falling back to `secrets_nugget.compile_config`.
- PySide6 UI artifacts trigger numerous type diagnostics; ignore unless a targeted fix is requested.

## Actions Completed (2025-12-13)
- [x] Stabilize translator locale retrieval by guarding the return value so Pyright sees a `str` (see `controllers/translator.py`).
- [x] Replace direct `_MEIPASS` access with `getattr(sys, "_MEIPASS", getcwd())` to satisfy the type checker while keeping PyInstaller compatibility (`controllers/files_handler.py`).
- [x] Enumerate CI/release secrets and data expectations for deployment readiness.

## Deployment Recommendations
1. **Secrets & Signing** – On GitHub, define secrets at repo level:
   - `MACOS_CODESIGN_IDENTITY` (identity string) and `MACOS_CODESIGN_HASH` (fingerprint) for notarization/signing steps.
   - `APPLE_NOTARY_TOKEN`, `APPLE_NOTARY_KEY`, and `APPLE_NOTARY_ISSUER` to drive notarization.
   - `WINDOWS_SIGN_CERT_PFX` and password if packaging signed builds.
2. **Artifact verification** – After pushing a test tag, confirm:
   - CI builds for macOS, Windows, and Linux complete successfully.
   - `softprops/action-gh-release` uploads `Nugget` assets and `sha256s.txt`.
   - Notarization output is attached to the macOS build (log mention).
3. **Installer packaging** – Keep tracking ffmpeg bundling and AppImage generation flags; rerun `build_macos.sh` and `build_linux.sh` locally when dependency versions change.
4. **Documentation audit** – Sync `RUNNING_INSTRUCTIONS.md` with the release workflow, highlight required environment files, and call out where user-provided `secrets_nugget/compile_config.py` is expected.
5. **Data leakage checks** – Ensure UDIDs or other device identifiers never leave the local machine unmasked; confirm log statements from `restore/restore.py` and `devicemanagement/device_manager.py` do not echo sensitive values in release builds.
