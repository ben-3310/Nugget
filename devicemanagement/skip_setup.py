"""
Skip Setup module for Nugget.

This module handles the generation of configuration files that allow
skipping the iOS setup wizard after a restore operation.
"""

import plistlib
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from pymobiledevice3.ca import create_keybag_file
from pymobiledevice3.services.mobile_config import MobileConfigService
from pymobiledevice3.lockdown import LockdownClient

from restore.restore import FileToRestore


# Complete list of setup screens that can be skipped
SKIP_SETUP_SCREENS = [
    "Location",
    "Restore",
    "SIMSetup",
    "Android",
    "AppleID",
    "IntendedUser",
    "TOS",
    "Siri",
    "ScreenTime",
    "Diagnostics",
    "SoftwareUpdate",
    "Passcode",
    "Biometric",
    "Payment",
    "Zoom",
    "DisplayTone",
    "MessagingActivationUsingPhoneNumber",
    "HomeButtonSensitivity",
    "CloudStorage",
    "ScreenSaver",
    "TapToSetup",
    "Keyboard",
    "PreferredLanguage",
    "SpokenLanguage",
    "WatchMigration",
    "OnBoarding",
    "TVProviderSignIn",
    "TVHomeScreenSync",
    "Privacy",
    "TVRoom",
    "iMessageAndFaceTime",
    "AppStore",
    "Safety",
    "Multitasking",
    "ActionButton",
    "TermsOfAddress",
    "AccessibilityAppearance",
    "Welcome",
    "Appearance",
    "RestoreCompleted",
    "UpdateCompleted",
    "WiFi",
    "Display",
    "Tone",
    "LanguageAndLocale",
    "TouchID",
    "TrueToneDisplay",
    "FileVault",
    "iCloudStorage",
    "iCloudDiagnostics",
    "Registration",
    "DeviceToDeviceMigration",
    "UnlockWithWatch",
    "Accessibility",
    "All",
    "ExpressLanguage",
    "Language",
    "N/A",
    "Region",
    "Avatar",
    "DeviceProtection",
    "Key",
    "LockdownMode",
    "Wallpaper",
    "PrivacySubtitle",
    "SecuritySubtitle",
    "DataSubtitle",
    "AppleIDSubtitle",
    "AppearanceSubtitle",
    "PreferredLang",
    "OnboardingSubtitle",
    "AppleTVSubtitle",
    "Intelligence",
    "WebContentFiltering",
    "CameraButton",
    "AdditionalPrivacySettings",
    "EnableLockdownMode",
    "OSShowcase",
    "SafetyAndHandling",
    "Tips",
    "AgeBasedSafetySettings",
]


def generate_cloud_config(
    lockdown_client: LockdownClient,
    supervised: bool = False,
    organization_name: str = None,
) -> dict:
    """
    Generate cloud configuration plist with skip setup options.

    Args:
        lockdown_client: The lockdown client for the device
        supervised: Whether to mark device as supervised
        organization_name: Organization name for supervision (optional)

    Returns:
        dict: Cloud configuration plist data
    """
    # Get the existing cloud config
    cloud_config = MobileConfigService(
        lockdown=lockdown_client
    ).get_cloud_configuration()

    # Add skip setup screens
    cloud_config["SkipSetup"] = SKIP_SETUP_SCREENS.copy()

    # Set basic configuration flags
    cloud_config["AllowPairing"] = True
    cloud_config["ConfigurationWasApplied"] = True
    cloud_config["CloudConfigurationUIComplete"] = True
    cloud_config["IsSupervised"] = False
    cloud_config["ConfigurationSource"] = 0
    cloud_config["PostSetupProfileWasInstalled"] = True

    # Handle supervision
    if supervised:
        cloud_config["IsSupervised"] = True

        if organization_name:
            with TemporaryDirectory() as temp_dir:
                keybag_file = Path(temp_dir) / "keybag"
                create_keybag_file(keybag_file, organization_name)
                cer = x509.load_pem_x509_certificate(keybag_file.read_bytes())
                public_key = cer.public_bytes(Encoding.DER)

                cloud_config["OrganizationName"] = organization_name
                cloud_config["OrganizationMagic"] = str(uuid4())
                cloud_config["IsMDMUnremovable"] = False
                cloud_config["SupervisorHostCertificates"] = [public_key]
        else:
            # Remove keybag info if no organization name
            cloud_config.pop("OrganizationMagic", None)
            cloud_config.pop("SupervisorHostCertificates", None)

    return cloud_config


def generate_purplebuddy_plist() -> dict:
    """
    Generate purplebuddy plist marking setup as complete.

    Returns:
        dict: Purplebuddy plist data
    """
    return {"SetupDone": True, "SetupFinishedAllSteps": True, "UserChoseLanguage": True}


def add_skip_setup_files(
    files_to_restore: list[FileToRestore],
    lockdown_client: LockdownClient,
    supervised: bool = False,
    organization_name: str = None,
):
    """
    Add skip setup configuration files to the restore list.

    Args:
        files_to_restore: List to append files to
        lockdown_client: The lockdown client for the device
        supervised: Whether to mark device as supervised
        organization_name: Organization name for supervision (optional)
    """
    # Generate and add cloud configuration
    cloud_config = generate_cloud_config(
        lockdown_client=lockdown_client,
        supervised=supervised,
        organization_name=organization_name,
    )
    files_to_restore.append(
        FileToRestore(
            contents=plistlib.dumps(cloud_config),
            restore_path="Library/ConfigurationProfiles/CloudConfigurationDetails.plist",
            domain="SysSharedContainerDomain-systemgroup.com.apple.configurationprofiles",
        )
    )

    # Generate and add purplebuddy plist
    purplebuddy = generate_purplebuddy_plist()
    files_to_restore.append(
        FileToRestore(
            contents=plistlib.dumps(purplebuddy),
            restore_path="mobile/com.apple.purplebuddy.plist",
            domain="ManagedPreferencesDomain",
        )
    )
