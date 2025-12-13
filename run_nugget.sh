#!/usr/bin/env bash

# NOTE: This is a shell script. Run it like:
#   ./run_nugget.sh
# or:
#   bash run_nugget.sh
# (Do not run it with python.)

set -e

OS="$(uname -s)"

# macOS doesn't use Xvfb for local GUI runs; just launch the app.
if [[ "${OS}" == "Darwin" ]]; then
    echo "macOS detected — starting Nugget directly..."
    exec python3 main_app.py
fi

# Check if Xvfb is running, if not start it (Linux/headless)
if command -v Xvfb >/dev/null 2>&1; then
    if ! pgrep -x "Xvfb" > /dev/null; then
        echo "Starting virtual display (Xvfb)..."
        Xvfb :99 -screen 0 1024x768x24 &
        sleep 2
    fi

    # Set display
    export DISPLAY=:99
else
    echo "Xvfb not found; continuing without a virtual display."
fi

# Check if usbmuxd is running, if not try to start it
if command -v usbmuxd >/dev/null 2>&1; then
    if ! pgrep -x "usbmuxd" > /dev/null; then
        echo "Starting usbmuxd service..."
        # Use non-interactive sudo to avoid hanging on a password prompt.
        if sudo -n true 2>/dev/null; then
            sudo -n usbmuxd -f &
            sleep 1
        else
            echo "sudo is required to start usbmuxd. Run: sudo usbmuxd -f &"
        fi
    fi
fi

echo "Starting Nugget application..."
exec python3 main_app.py
