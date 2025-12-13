# Nugget Application - Running Instructions

## ✅ Installation Complete

The Nugget application has been successfully set up and all dependencies have been installed.

## 📋 System Requirements Installed

- **Python 3.12.3** ✓
- **PySide6** (Qt for Python) ✓
- **pymobiledevice3** (iOS device management) ✓
- **All Qt system libraries** ✓
- **Virtual display (Xvfb)** ✓
- **iOS device support libraries** (usbmuxd, libimobiledevice) ✓

## 🚀 How to Run Nugget

### Option 1: Using the Launch Script (Recommended)
```bash
./run_nugget.sh
```
This script automatically:
- Starts a virtual display if needed
- Starts usbmuxd service for iOS device support
- Launches the Nugget application

### Option 2: Manual Launch with Virtual Display
```bash
# Start virtual display
Xvfb :99 -screen 0 1024x768x24 &

# Set display environment variable
export DISPLAY=:99

# Run the application
python3 main_app.py
```

### Option 3: Offscreen Mode (No display needed)
```bash
QT_QPA_PLATFORM=offscreen python3 main_app.py
```

## 🔍 Testing the Installation

Run the test script to verify all components:
```bash
python3 test_nugget.py
```

## ⚠️ Notes

1. **iOS Device Connection**: The application may show a warning about failing to get the device list. This is normal if no iOS devices are connected via USB.

2. **Running in Headless Environment**: Since this is running in a cloud/remote environment without a physical display, the application uses a virtual display (Xvfb) to render the GUI.

3. **Permissions**: Some features may require sudo permissions, especially when working with iOS devices.

## 📱 About Nugget

Nugget is a tool for iOS device customization and management. It provides various tweaks and modifications for iOS devices, including:
- Status bar customization
- Eligibility tweaks
- Posterboard modifications
- Device management features

## 🛠️ Troubleshooting

If you encounter any issues:

1. **Qt Platform Error**: Make sure all Qt libraries are installed:
   ```bash
   sudo apt-get install libxcb-cursor0 libgl1 libegl1
   ```

2. **iOS Device Not Detected**: Ensure usbmuxd is running:
   ```bash
   sudo usbmuxd -f &
   ```

3. **Import Errors**: Reinstall dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

## ✨ Successfully Configured!

The application is now ready to use. Connect an iOS device via USB to access all features.