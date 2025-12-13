# Nugget Architecture

## Overview

Nugget is a Python-based iOS customization tool that uses exploit techniques (Sparserestore/BookRestore) to modify system files on iOS devices.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  main_app   │──│ MainWindow  │──│   Pages     │──│  Qt UI Components   │ │
│  │   (Entry)   │  │   (GUI)     │  │  (Views)    │  │  (mainwindow.ui)    │ │
│  └─────────────┘  └──────┬──────┘  └─────────────┘  └─────────────────────┘ │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│                          DEVICE MANAGEMENT                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      DeviceManager                                       ││
│  │  - get_devices()     : Detect connected iOS devices                      ││
│  │  - apply_changes()   : Apply all enabled tweaks                          ││
│  │  - reset_tweaks()    : Reset tweaks to default                           ││
│  │  - start_restore()   : Execute restore process                           ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────────┐ │
│  │ PreferencesMgr │  │ DataSingleton  │  │       Device/Version           │ │
│  │ (User Prefs)   │  │ (App State)    │  │    (Device Constants)          │ │
│  └────────────────┘  └────────────────┘  └────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│                           TWEAKS SYSTEM                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         tweaks (dict)                                    ││
│  │  TweakID.PosterBoard  → PosterboardTweak                                 ││
│  │  TweakID.Templates    → TemplatesTweak                                   ││
│  │  TweakID.StatusBar    → StatusBarTweak                                   ││
│  │  TweakID.*            → MobileGestaltTweak / BasicPlistTweak / etc.      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ MobileGestalt   │  │ FeatureFlag     │  │    BasicPlistTweak          │  │
│  │    Tweaks       │  │    Tweaks       │  │  AdvancedPlistTweak         │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  Eligibility    │  │   Posterboard   │  │      StatusBar              │  │
│  │    Tweaks       │  │     Tweaks      │  │       Tweaks                │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│                         RESTORE SYSTEM                                       │
│  ┌───────────────────────────────────────┬─────────────────────────────────┐│
│  │          Sparserestore                │         BookRestore             ││
│  │        (iOS 17.0-18.1.1)              │       (iOS 18.2-26.1)           ││
│  ├───────────────────────────────────────┼─────────────────────────────────┤│
│  │  restore_files()                      │  perform_bookrestore()          ││
│  │  - Creates backup structure           │  - Creates tunnel to device     ││
│  │  - Uses domain path traversal         │  - Manipulates Books app DB     ││
│  │  - Restores via MobileBackup2         │  - Overwrites files via AFC     ││
│  └───────────────────────────────────────┴─────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        FileToRestore                                     ││
│  │  - contents: bytes     (file data)                                       ││
│  │  - restore_path: str   (target path on device)                           ││
│  │  - domain: str         (backup domain)                                   ││
│  │  - owner/group: int    (file permissions)                                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│                        iOS DEVICE                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  pymobiledevice3 Services:                                               ││
│  │  - LockdownClient      : Device connection                               ││
│  │  - Mobilebackup2       : Backup/Restore service                          ││
│  │  - AfcService          : File system access                              ││
│  │  - DiagnosticsService  : Device reboot                                   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Application Startup
```
main_app.py
    │
    ├── QApplication created
    ├── DeviceManager initialized
    ├── Translator loaded (i18n)
    │
    └── MainWindow created
        ├── UI setup from mainwindow.ui
        ├── Pages pre-loaded (Home, Posterboard, Gestalt, etc.)
        ├── Settings loaded
        └── Device refresh triggered
```

### 2. Device Connection Flow
```
MainWindow.refresh_devices()
    │
    └── RefreshDevicesThread
        │
        └── DeviceManager.get_devices()
            │
            ├── usbmux.list_devices()
            ├── create_using_usbmux() for each device
            ├── Read device info (name, version, model, etc.)
            └── Set current device
```

### 3. Apply Tweaks Flow
```
MainWindow.apply_changes()
    │
    └── ApplyThread
        │
        └── DeviceManager.apply_changes()
            │
            ├── Collect enabled tweaks
            │   ├── FeatureFlagTweak.apply_tweak()
            │   ├── EligibilityTweak.apply_tweak()
            │   ├── BasicPlistTweak.apply_tweak()
            │   ├── PosterboardTweak.apply_tweak()
            │   ├── TemplatesTweak.apply_tweak()
            │   ├── StatusBarTweak.apply_tweak()
            │   └── MobileGestaltTweak.apply_tweak()
            │
            ├── Generate FileToRestore list
            │
            └── DeviceManager.start_restore()
                │
                ├── [iOS 17.0-18.1.1] restore_files() (Sparserestore)
                │   └── Mobilebackup2Service.restore()
                │
                └── [iOS 18.2-26.1] perform_bookrestore()
                    ├── Create tunnel
                    ├── AFC file operations
                    └── Books app DB manipulation
```

## Key Modules

### `/main_app.py`
Entry point. Initializes QApplication, DeviceManager, Translator, and MainWindow.

### `/gui/`
- `main_window.py` - Main application window with page navigation
- `apply_worker.py` - QThread workers for async operations
- `pages/` - Individual page implementations (Home, Posterboard, Gestalt, etc.)
- `dialogs.py` - Modal dialogs

### `/devicemanagement/`
- `device_manager.py` - Core device operations and tweak application
- `constants.py` - Device and Version classes
- `data_singleton.py` - Application state
- `preference_manager.py` - User preferences storage

### `/tweaks/`
- `tweaks.py` - Global tweaks dictionary
- `tweak_classes.py` - Base tweak classes
- `tweak_loader.py` - Dynamic tweak loading based on iOS version
- `tweak_names.py` - TweakID enum
- `posterboard/` - PosterBoard wallpaper tweaks
- `status_bar/` - Status bar customization

### `/restore/`
- `restore.py` - Sparserestore implementation
- `bookrestore.py` - BookRestore implementation
- `backup.py` - Backup structure creation
- `mbdb.py` - Mobile backup database handling

### `/controllers/`
- `files_handler.py` - File operations
- `plist_handler.py` - Plist manipulation
- `video_handler.py` - Video processing for wallpapers
- `translator.py` - Internationalization
- `xml_handler.py` - XML processing

## Tweak Types

| Type                 | Description                  | Example                      |
| -------------------- | ---------------------------- | ---------------------------- |
| `MobileGestaltTweak` | Modifies MobileGestalt.plist | Dynamic Island, Boot Chime   |
| `FeatureFlagTweak`   | Toggles iOS feature flags    | Clock Animation, AI Features |
| `BasicPlistTweak`    | Modifies simple plist keys   | Lock Screen Footnote         |
| `AdvancedPlistTweak` | Modifies multiple plist keys | Daemon disable               |
| `EligibilityTweak`   | EU/AI eligibility files      | EU Enabler                   |
| `PosterboardTweak`   | Animated wallpapers          | .tendies files               |
| `TemplatesTweak`     | Custom templates             | .batter files                |
| `StatusBarTweak`     | Status bar customization     | Carrier name, icons          |

## File Formats

### .tendies (PosterBoard Wallpapers)
Contains wallpaper files in `container/` or `descriptor/` folder structure.

### .batter (Templates)
JSON config with customizable options + file structure to restore.

## Exploit Methods

### Sparserestore (iOS 17.0-18.1.1)
Uses path traversal in backup domain names to write files outside intended restore location.

### BookRestore (iOS 18.2-26.1)
Manipulates Books app download database to trigger file overwrites via itunesstored.
