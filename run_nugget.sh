#!/bin/bash

# Check if Xvfb is running, if not start it
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "Starting virtual display (Xvfb)..."
    Xvfb :99 -screen 0 1024x768x24 &
    sleep 2
fi

# Set display
export DISPLAY=:99

# Check if usbmuxd is running, if not try to start it
if ! pgrep -x "usbmuxd" > /dev/null; then
    echo "Starting usbmuxd service..."
    sudo usbmuxd -f &
    sleep 1
fi

echo "Starting Nugget application..."
python3 main_app.py