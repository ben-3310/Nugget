# Troubleshooting

This document collects the most common problems reported by users and the fastest fixes.

## BookRestore (iOS 18.2 – 26.1)

### Quick checklist

1. **USB connection**: use a known-good cable/port (avoid hubs if possible).
2. **Device unlocked + trusted**: unlock the device and tap **Trust** when prompted.
3. **Find My OFF**: Settings → *[your name]* → **Find My** → disable **Find My iPhone** (turn it back on after you’re done).
4. **Developer Mode (AFC method)**: Settings → Privacy & Security → **Developer Mode**.
5. **Books app requirement**: open **Books** and download at least one book before applying BookRestore tweaks.

### “Waiting for itunesstored to finish download…” / timeouts

- **What it means**: BookRestore is waiting for the Books download pipeline to advance.
- **Fixes**:
  - Open **Books**, start a download, wait until it completes, then retry.
  - Keep the device unlocked during the whole apply.
  - Prefer USB (disable “Apply over Wi‑Fi”).
  - Try switching **BookRestore apply mode** to **Restore** (Settings page).
  - Reboot the device and your computer and retry.

### “You must run the application as an administrator…”

- **Windows**: run Nugget as Administrator for some BookRestore operations.

### “You must enable developer mode on your device…”

- Enable **Developer Mode** (Settings → Privacy & Security → Developer Mode), reboot when prompted, then retry.

### “Find My must be disabled…”

- Disable **Find My iPhone** and retry. Re-enable it after you’re done.

## PosterBoard / Wallpapers

### Wallpapers not appearing / gallery disappeared / weird zoom/crop

- Try applying **one thing at a time** (avoid large batches when debugging).
- Use the PosterBoard **Reset** dropdown in the PosterBoard tools page:
  - **Collections**
  - **Suggested Photos**
  - **Gallery Cache**
- Apply the reset, then reboot/respring and check again.
- If video wallpapers look zoomed/cropped:
  - Try a different resolution/aspect ratio source video.
  - Re-export using the built-in conversion tools.

## “Device not detected”

- Unlock the device and tap **Trust**.
- Try a different cable/port.
- On Linux: ensure `usbmuxd` and `libimobiledevice` are installed (see README requirements).

## iOS 26.2+ (Fully patched / limited support)

- MobileGestalt and AI Enabler tweaks are **not supported** on iOS 26.2+ and will never be supported.
- Some non-MobileGestalt tweaks may still work, but results vary by device/iOS build.


