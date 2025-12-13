#!/usr/bin/env python3
"""Test script to verify Nugget components are working"""

import sys
import os

def test_imports():
    """Test if all main imports work"""
    print("Testing imports...")
    
    try:
        from PySide6 import QtGui, QtWidgets, QtCore
        print("✓ PySide6 imported successfully")
    except ImportError as e:
        print(f"✗ PySide6 import failed: {e}")
        return False
    
    try:
        from controllers.translator import Translator
        print("✓ Translator imported successfully")
    except ImportError as e:
        print(f"✗ Translator import failed: {e}")
        return False
    
    try:
        from gui.main_window import MainWindow
        print("✓ MainWindow imported successfully")
    except ImportError as e:
        print(f"✗ MainWindow import failed: {e}")
        return False
    
    try:
        from devicemanagement.device_manager import DeviceManager
        print("✓ DeviceManager imported successfully")
    except ImportError as e:
        print(f"✗ DeviceManager import failed: {e}")
        return False
    
    try:
        from tweaks.tweaks import tweaks, TweakID
        print("✓ Tweaks imported successfully")
    except ImportError as e:
        print(f"✗ Tweaks import failed: {e}")
        return False
    
    try:
        import pymobiledevice3
        print("✓ pymobiledevice3 imported successfully")
    except ImportError as e:
        print(f"✗ pymobiledevice3 import failed: {e}")
        return False
    
    return True

def test_qt_platform():
    """Test Qt platform availability"""
    print("\nTesting Qt platform...")
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    try:
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
        print(f"✓ Qt application created successfully")
        print(f"  Platform: {app.platformName()}")
        return True
    except Exception as e:
        print(f"✗ Qt platform test failed: {e}")
        return False

def test_device_manager():
    """Test device manager initialization"""
    print("\nTesting Device Manager...")
    
    try:
        from devicemanagement.device_manager import DeviceManager
        dm = DeviceManager()
        print("✓ DeviceManager initialized successfully")
        
        # Try to get device list (may fail if no devices connected)
        try:
            dm.get_device_list()
            print("✓ Device list retrieved (or no devices found)")
        except Exception as e:
            print(f"⚠ Device list retrieval warning: {e}")
            print("  This is expected if no iOS devices are connected")
        
        return True
    except Exception as e:
        print(f"✗ DeviceManager test failed: {e}")
        return False

def main():
    print("="*50)
    print("Nugget Application Test Suite")
    print("="*50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test Qt platform
    if not test_qt_platform():
        all_passed = False
    
    # Test device manager
    if not test_device_manager():
        all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✓ All tests passed! Nugget is ready to run.")
        print("\nTo run Nugget:")
        print("  1. With virtual display: ./run_nugget.sh")
        print("  2. In offscreen mode: QT_QPA_PLATFORM=offscreen python3 main_app.py")
    else:
        print("✗ Some tests failed. Please check the errors above.")
    print("="*50)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())