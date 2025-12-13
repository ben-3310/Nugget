"""
Nugget Compilation Script

This script compiles Nugget into a standalone executable using PyInstaller.
Supports macOS, Windows, and Linux with platform-specific configurations.

Usage:
    python compile.py                    # Build for current platform
    python compile.py --target-arch=arm64  # Build for specific architecture (macOS)
"""

from sys import platform, argv
import os
import importlib
from typing import Any, Optional
import PyInstaller.__main__

print("=" * 50)
print("       Nugget Compilation Script")
print("=" * 50)
print(f"Platform: {platform}")
print(f"Working directory: {os.getcwd()}")

target_arch = next((arg for arg in argv if arg.startswith("--target-arch=")), None)
if target_arch:
    print(f"[+] Target arch: {target_arch}")

# Base PyInstaller args
args = [
    'main_app.py',
    '--name=Nugget',
    '--icon=nugget.ico',
    '--onedir',
    '--noconfirm',
    '--collect-all=devicemanagement',
    '--collect-all=pymobiledevice3',  # Forces inclusion of __main__.py
    '--collect-all=utils',  # Include logging utilities
    '--add-data=files/:files',
    '--copy-metadata=pyimg4',
    '--hidden-import=zeroconf',
    '--hidden-import=pyimg4',
    '--hidden-import=zeroconf._utils.ipaddress',
    '--hidden-import=zeroconf._handlers.answers',
    '--hidden-import=inquirer',
    '--hidden-import=readchar',
    '--hidden-import=logging',
    '--copy-metadata=readchar'
]

if target_arch:
    args.append(target_arch)

# macOS-specific flags
if platform == "darwin":
    print("\n[+] Configuring for macOS...")
    args.append('--windowed')
    args.append('--osx-bundle-identifier=com.leemin.Nugget')

    # Add icon data for macOS
    args.append('--add-data=nugget.ico:.')
    args.append('--add-data=credits/:credits')
    args.append('--add-data=icon/:icon')

    codesign_hash = os.getenv("NUGGET_CODESIGN_HASH")
    if codesign_hash:
        print("[+] Code signing configuration found (env: NUGGET_CODESIGN_HASH)")
        args.append('--osx-entitlements-file=entitlements.plist')
        args.append(f"--codesign-identity={codesign_hash}")
    else:
        compile_config: Optional[Any] = None
        try:
            # Optional, user-provided config (not committed to the repo).
            # Use importlib to avoid static type-check "missing import" errors.
            compile_config = importlib.import_module("secrets_nugget.compile_config")
        except ModuleNotFoundError:
            compile_config = None
        except Exception:
            compile_config = None

        if compile_config is not None and getattr(
            compile_config, "CODESIGN_HASH", None
        ):
            print("[+] Code signing configuration found (secrets_nugget/compile_config.py)")
            args.append('--osx-entitlements-file=entitlements.plist')
            args.append(f"--codesign-identity={compile_config.CODESIGN_HASH}")
        else:
            print("[!] Codesign skipped: no configuration found")
            print("    Set NUGGET_CODESIGN_HASH or create secrets_nugget/compile_config.py with CODESIGN_HASH")

elif os.name == 'nt':
    print("\n[+] Configuring for Windows...")
    args.append('--version-file=version.txt')
    args.append('--add-binary=status_setter_windows.exe;.')
    args.append('--add-data=nugget.ico;.')
    args.append('--add-data=credits/;credits')
    args.append('--add-data=icon/;icon')

    try:
        import pytun_pmd3
        package_path = os.path.dirname(pytun_pmd3.__file__)
        print(f"[+] Found pytun_pmd3 at: {package_path}")
        args.append('--add-binary')
        args.append(f"{package_path}/*;pytun_pmd3")
    except ImportError:
        print("[!] ERROR: Could not import pytun_pmd3. Ensure it is installed with pip.")
        import site
        site_packages_path = site.getsitepackages()[1]
        args.append('--add-binary')
        args.append(f"{site_packages_path}/pytun_pmd3/*;pytun_pmd3")

    if os.path.isdir("ffmpeg/bin"):
        args.append('--add-data=ffmpeg/bin;ffmpeg/bin')
    else:
        print("[!] ffmpeg not bundled: folder not found")

else:
    print("\n[+] Configuring for Linux...")
    args.append('--add-data=nugget.ico:.')
    args.append('--add-data=credits/:credits')
    args.append('--add-data=icon/:icon')

print("\n[+] Starting PyInstaller...")
print(f"    Args: {len(args)} arguments")
print("-" * 50)

PyInstaller.__main__.run(args)

print("-" * 50)
print("[+] Compilation complete!")
