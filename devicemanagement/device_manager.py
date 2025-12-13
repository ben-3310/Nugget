import traceback
import plistlib
import time
from dataclasses import dataclass
from enum import Enum
from tempfile import TemporaryDirectory
from typing import Optional
import os.path

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QSettings, QCoreApplication

from pymobiledevice3 import usbmux
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.exceptions import MuxException, PasswordRequiredError, ConnectionTerminatedError, AccessDeniedError, InvalidServiceError
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.services.house_arrest import HouseArrestService
from pymobiledevice3.services.afc import AfcService

from devicemanagement.constants import Device, Version
from devicemanagement.data_singleton import DataSingleton
from devicemanagement.skip_setup import add_skip_setup_files
from .preference_manager import PreferenceManager

from gui.apply_worker import ApplyAlertMessage
from gui.pages.pages_list import Page
from controllers.path_handler import fix_windows_path
from controllers.files_handler import get_bundle_files

from exceptions.nugget_exception import NuggetException

from tweaks.tweaks import tweaks, TweakID, FeatureFlagTweak, EligibilityTweak, AITweak, BasicPlistTweak, AdvancedPlistTweak, RdarFixTweak, NullifyFileTweak, StatusBarTweak
from tweaks.tweak_classes import (
    MobileGestaltCacheDataTweak,
    MobileGestaltMultiTweak,
    MobileGestaltPickerTweak,
    MobileGestaltTweak,
)
from tweaks.custom_gestalt_tweaks import CustomGestaltTweaks
from tweaks.posterboard.posterboard_tweak import PosterboardTweak
from tweaks.posterboard.template_options.templates_tweak import TemplatesTweak
from tweaks.basic_plist_locations import FileLocation

from restore import reboot_device
from restore.restore import restore_files, FileToRestore
from restore.bookrestore import perform_bookrestore, create_server_folder, create_local_server, cleanup_server_folder, close_dl_connection, generate_bldbmanager, br_files
from restore.bookrestore_types import BookRestoreFileTransferMethod, BookRestoreApplyMethod
from restore.mbdb import _FileMode


def show_error_msg(
    txt: str,
    title: str = "Error!",
    icon: QMessageBox.Icon = QMessageBox.Icon.Critical,
    detailed_txt: Optional[str] = None,
):
    detailsBox = QMessageBox()
    detailsBox.setIcon(icon)
    detailsBox.setWindowTitle(title)
    detailsBox.setText(txt)
    if detailed_txt is not None:
        detailsBox.setDetailedText(detailed_txt)
    detailsBox.exec()


def get_files_list_str(files_list: Optional[list[FileToRestore]] = None) -> str:
    files_str: str = ""
    if files_list is not None:
        files_str = "FILES LIST:"
        print("\nFile List:\n")
        for file in files_list:
            file_info = f"\n    Domain: {file.domain}\n    Path: {file.restore_path}"
            files_str += file_info
            print(file_info)
        files_str += "\n\n"
    return files_str


def show_apply_error(
    e: Exception,
    update_label=lambda x: None,
    files_list: Optional[list[FileToRestore]] = None,
):
    print(traceback.format_exc())
    update_label("Failed to restore")
    if "Find My" in str(e):
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "Find My must be disabled in order to use this tool.",
            ),
            detailed_txt=QCoreApplication.translate(
                "QCoreApplication",
                "Disable Find My from Settings (Settings -> [Your Name] -> Find My) and then try again.",
            ),
        )
    elif "Encrypted Backup MDM" in str(e):
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "Nugget cannot be used on this device. Click Show Details for more info.",
            ),
            detailed_txt=QCoreApplication.translate(
                "QCoreApplication",
                "Your device is managed and MDM backup encryption is on. This must be turned off in order for Nugget to work. Please do not use Nugget on your school/work device!",
            ),
        )
    elif "SessionInactive" in str(e) or "ConnectionAbortedError" in str(e):
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "The session was terminated. Refresh the device list and try again.",
            )
        )
    elif "PasswordRequiredError" in str(e):
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "Device is password protected! You must trust the computer on your device.",
            ),
            detailed_txt=QCoreApplication.translate(
                "QCoreApplication",
                'Unlock your device. On the popup, click "Trust", enter your password, then try again.',
            ),
        )
    elif isinstance(e, ConnectionTerminatedError):
        files_str: str = get_files_list_str(files_list)
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "Device failed in sending files. The file list is possibly corrupted or has duplicates. Click Show Details for more info.",
            ),
            detailed_txt=files_str + "TRACEBACK:\n\n" + str(traceback.format_exc()),
        )
    elif isinstance(e, AccessDeniedError):
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "You must run the application as an administrator to use BookRestore tweaks.",
            ),
            detailed_txt="Try running the program with sudo.",
        )
    elif isinstance(e, InvalidServiceError):
        return ApplyAlertMessage(
            QCoreApplication.translate(
                "QCoreApplication",
                "You must enable developer mode on your device. You can do it in the Settings app.",
            ),
            detailed_txt=QCoreApplication.translate(
                "QCoreApplication",
                "BookRestore tweaks with the AFC method require developer mode to apply.\n\nYou can enable this at the bottom of Settings > Privacy & Security > Developer Mode on your iPhone or iPad.",
            ),
        )
    elif isinstance(e, NuggetException):
        return ApplyAlertMessage(str(e), detailed_txt=e.detailed_text)
    else:
        files_str = get_files_list_str(files_list)
        return ApplyAlertMessage(type(e).__name__ + ": " + repr(e), detailed_txt=files_str + "TRACEBACK:\n\n" + str(traceback.format_exc()))


class PreflightStatus(Enum):
    OK = "ok"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class PreflightCheck:
    """
    A single preflight check result shown to the user before applying tweaks.
    """

    status: PreflightStatus
    title: str
    message: str
    remediation: str | None = None
    details: str | None = None


@dataclass(frozen=True)
class PreflightResult:
    checks: list[PreflightCheck]

    @property
    def has_blockers(self) -> bool:
        return any(c.status == PreflightStatus.BLOCK for c in self.checks)

class DeviceManager:
    """
    Main device management class for Nugget.

    This class handles:
    - Device detection and connection via usbmuxd
    - Tweak application and management
    - Restore operations (Sparserestore and BookRestore)
    - User preferences and settings

    Attributes:
        devices: List of connected iOS devices
        data_singleton: Shared application state
        current_device_index: Index of currently selected device
        pref_manager: User preferences manager
    """

    def __init__(self):
        """Initialize the DeviceManager with empty device list and default settings."""
        self.devices: list[Device] = []
        self.data_singleton = DataSingleton()
        self.current_device_index = 0
        self.pref_manager = PreferenceManager(None)

    def get_devices(self, settings: QSettings, show_alert=lambda x: None):
        """
        Detect and connect to iOS devices via usbmuxd.

        Scans for connected devices and creates Device objects for each.
        Sets the first device as current if any are found.

        Args:
            settings: QSettings instance for persisting device info
            show_alert: Callback for displaying error alerts
        """
        self.devices.clear()
        if self.pref_manager.settings == None:
            self.pref_manager.settings = settings
        # handle errors when failing to get connected devices
        try:
            connected_devices = usbmux.list_devices()
        except Exception:
            sysmsg = QCoreApplication.translate(
                "QCoreApplication",
                "If you are on Linux, make sure you have usbmuxd and libimobiledevice installed.",
            )
            if os.name == 'nt':
                sysmsg = QCoreApplication.translate(
                    "QCoreApplication",
                    'Make sure you have the "Apple Devices" app from the Microsoft Store or iTunes from Apple\'s website.',
                )
            show_alert(
                ApplyAlertMessage(
                    txt=QCoreApplication.translate(
                        "QCoreApplication",
                        'Failed to get device list. Click "Show Details" for the traceback.',
                    )
                    + f"\n\n{sysmsg}",
                    detailed_txt=str(traceback.format_exc()),
                )
            )
            self.set_current_device(index=None)
            return
        # Connect via usbmuxd
        for device in connected_devices:
            if self.pref_manager.apply_over_wifi or device.is_usb:
                try:
                    # usbmux "serial" may be typed as int by stubs; normalize to str for
                    # QSettings key building and lockdown APIs.
                    serial = str(device.serial)
                    ld = create_using_usbmux(serial=serial)
                    vals = ld.all_values
                    if vals is None:
                        continue
                    model = str(vals.get("ProductType", ""))
                    hardware = str(vals.get("HardwareModel", ""))
                    cpu = str(vals.get("HardwarePlatform", ""))
                    try:
                        product_type = settings.value(f"{serial}_model", "", type=str)
                        hardware_type = settings.value(
                            f"{serial}_hardware", "", type=str
                        )
                        cpu_type = settings.value(f"{serial}_cpu", "", type=str)
                        books_uuid = settings.value(
                            f"{serial}_books_container_uuid", "", type=str
                        )
                        if product_type == "":
                            # save the new product type
                            settings.setValue(f"{serial}_model", model)
                        else:
                            model = product_type
                        if hardware_type == "":
                            # save the new hardware model
                            settings.setValue(f"{serial}_hardware", hardware)
                        else:
                            hardware = hardware_type
                        if cpu_type == "":
                            # save the new cpu model
                            settings.setValue(f"{serial}_cpu", cpu)
                        else:
                            cpu = cpu_type
                    except Exception:
                        show_alert(
                            ApplyAlertMessage(
                                txt=QCoreApplication.translate(
                                    "QCoreApplication",
                                    'Click "Show Details" for the traceback.',
                                ),
                                detailed_txt=str(traceback.format_exc()),
                            )
                        )
                    dev = Device(
                        udid=serial,
                        usb=device.is_usb,
                        name=str(vals.get("DeviceName", "")),
                        version=str(vals.get("ProductVersion", "")),
                        build=str(vals.get("BuildVersion", "")),
                        model=model,
                        hardware=hardware,
                        cpu=cpu,
                        locale=ld.locale,
                        books_container_uuid=str(books_uuid) if books_uuid else "",
                        ld=ld,
                    )
                    self.devices.append(dev)
                except PasswordRequiredError as e:
                    show_alert(
                        ApplyAlertMessage(
                            txt=QCoreApplication.translate(
                                "QCoreApplication",
                                'Device is password protected! You must trust the computer on your device.\n\nUnlock your device. On the popup, click "Trust", enter your password, then try again.',
                            )
                        )
                    )
                except MuxException as e:
                    # there is probably a cable issue
                    print(f"MUX ERROR with lockdown device with UUID {device.serial}")
                    show_alert(
                        ApplyAlertMessage(
                            txt="MuxException: "
                            + repr(e)
                            + "\n\n"
                            + QCoreApplication.translate(
                                "QCoreApplication",
                                "If you keep receiving this error, try using a different cable or port.",
                            ),
                            detailed_txt=str(traceback.format_exc()),
                        )
                    )
                except Exception as e:
                    print(f"ERROR with lockdown device with UUID {device.serial}")
                    show_alert(ApplyAlertMessage(txt=f"{type(e).__name__}: {repr(e)}", detailed_txt=str(traceback.format_exc())))

        if len(self.devices) > 0:
            self.set_current_device(index=0)
        else:
            self.set_current_device(index=None)

    ## CURRENT DEVICE
    def set_current_device(self, index: Optional[int] = None):
        if index == None or len(self.devices) == 0:
            self.data_singleton.current_device = None
            self.data_singleton.device_available = False
            self.data_singleton.gestalt_path = None
            self.current_device_index = 0
            if TweakID.SpoofModel in tweaks:
                tweaks[TweakID.SpoofModel].value[0] = "Placeholder"
                tweaks[TweakID.SpoofHardware].value[0] = "Placeholder"
                tweaks[TweakID.SpoofCPU].value[0] = "Placeholder"
        else:
            self.data_singleton.current_device = self.devices[index]
            if Version(self.devices[index].version) < Version("17.0"):
                self.data_singleton.device_available = False
                self.data_singleton.gestalt_path = None
            else:
                # load the mga file
                if self.pref_manager.has_valid_mga_data(self.get_current_device_udid(), self.get_current_device_build(), self.get_current_device_model()):
                    self.data_singleton.gestalt_path = self.data_singleton.SAVED_GESTALT_STRING
                else:
                    self.data_singleton.gestalt_path = None
                self.data_singleton.device_available = True
                if TweakID.SpoofModel in tweaks:
                    tweaks[TweakID.SpoofModel].value[0] = self.data_singleton.current_device.model
                    tweaks[TweakID.SpoofHardware].value[0] = self.data_singleton.current_device.hardware
                    tweaks[TweakID.SpoofCPU].value[0] = self.data_singleton.current_device.cpu
            self.current_device_index = index

    def run_preflight(self) -> PreflightResult:
        """
        Run non-destructive checks before applying tweaks.

        This is designed to catch common blockers early (device not connected,
        not trusted/unlocked, etc.) and provide actionable remediation steps.
        """
        checks: list[PreflightCheck] = []

        dev = self.data_singleton.current_device
        if dev is None:
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.BLOCK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "No device connected"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "Please connect an iPhone/iPad and refresh the device list.",
                    ),
                )
            )
            return PreflightResult(checks=checks)

        # Trust / lockdown availability
        try:
            _ = dev.ld.all_values
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.OK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Device connection"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication", "Device is connected and trusted."
                    ),
                )
            )
        except PasswordRequiredError:
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.BLOCK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Device locked / not trusted"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "Unlock your device and tap “Trust” when prompted, then refresh and try again.",
                    ),
                )
            )
        except Exception as e:
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.BLOCK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Device connection failed"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication", "Failed to query device via Lockdown."
                    ),
                    details=f"{type(e).__name__}: {e!r}",
                )
            )

        # iOS / exploit compatibility (high-level)
        device_ver = Version(dev.version)
        if device_ver < Version("17.0"):
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.BLOCK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Unsupported iOS version"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "This device is below iOS 17.0 and is not supported.",
                    ),
                )
            )
            return PreflightResult(checks=checks)

        if dev.has_partial_sparserestore():
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.OK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Restore method"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "Sparserestore is available on this iOS version.",
                    ),
                )
            )
        elif dev.has_bookrestore():
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.OK,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Restore method"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "BookRestore is available on this iOS version.",
                    ),
                )
            )
        else:
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.WARN,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Limited support"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "This device appears to be fully patched. Some tweaks may not apply on this iOS version.",
                    ),
                )
            )

        # Find My requirement (best-effort: we cannot reliably query the toggle via lockdown)
        checks.append(
            PreflightCheck(
                status=PreflightStatus.WARN,
                title=QCoreApplication.translate("QCoreApplication", "Find My"),
                message=QCoreApplication.translate(
                    "QCoreApplication",
                    "Find My must be disabled to apply tweaks. If you get a Find My error, disable it and try again.",
                ),
                remediation=QCoreApplication.translate(
                    "QCoreApplication",
                    "Settings → [your name] → Find My → disable Find My iPhone",
                ),
            )
        )

        # Developer Mode requirement (best-effort: we cannot reliably query this state pre-apply)
        if dev.has_bookrestore() and self.pref_manager.bookrestore_apply_mode == BookRestoreApplyMethod.AFC:
            checks.append(
                PreflightCheck(
                    status=PreflightStatus.WARN,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "Developer Mode"
                    ),
                    message=QCoreApplication.translate(
                        "QCoreApplication",
                        "BookRestore with the AFC method may require Developer Mode to be enabled.",
                    ),
                    remediation=QCoreApplication.translate(
                        "QCoreApplication",
                        "Settings → Privacy & Security → Developer Mode",
                    ),
                )
            )
            if os.name == "nt":
                checks.append(
                    PreflightCheck(
                        status=PreflightStatus.WARN,
                        title=QCoreApplication.translate(
                            "QCoreApplication", "Administrator privileges"
                        ),
                        message=QCoreApplication.translate(
                            "QCoreApplication",
                            "On Windows, some BookRestore operations may require running Nugget as Administrator.",
                        ),
                    )
                )

        # iOS 26.2+ explicitly blocks MobileGestalt + AI Enabler tweaks (per project policy)
        if device_ver >= Version("26.2"):
            blocked_enabled: list[str] = []
            for tweak in tweaks.values():
                try:
                    if not getattr(tweak, "enabled", False):
                        continue
                    if isinstance(
                        tweak,
                        (
                            AITweak,
                            MobileGestaltTweak,
                            MobileGestaltPickerTweak,
                            MobileGestaltMultiTweak,
                            MobileGestaltCacheDataTweak,
                        ),
                    ):
                        blocked_enabled.append(type(tweak).__name__)
                except Exception:
                    continue

            status = PreflightStatus.WARN if len(blocked_enabled) == 0 else PreflightStatus.BLOCK
            msg = QCoreApplication.translate(
                "QCoreApplication",
                "MobileGestalt and AI Enabler tweaks are not supported on iOS 26.2+. They will never be supported.",
            )
            if blocked_enabled:
                msg += QCoreApplication.translate(
                    "QCoreApplication",
                    "\n\nDisable MobileGestalt/AI toggles and try again.",
                )
            checks.append(
                PreflightCheck(
                    status=status,
                    title=QCoreApplication.translate(
                        "QCoreApplication", "iOS 26.2+ limitation"
                    ),
                    message=msg,
                    details=", ".join(blocked_enabled) if blocked_enabled else None,
                )
            )

        return PreflightResult(checks=checks)

    def get_current_device_name(self) -> str:
        if self.data_singleton.current_device == None:
            return QCoreApplication.translate("QCoreApplication", "No Device")
        else:
            return self.data_singleton.current_device.name

    def get_current_device_version(self) -> str:
        if self.data_singleton.current_device == None:
            return ""
        else:
            return self.data_singleton.current_device.version

    def get_current_device_build(self) -> str:
        if self.data_singleton.current_device == None:
            return ""
        else:
            return self.data_singleton.current_device.build

    def get_current_device_udid(self) -> str:
        if self.data_singleton.current_device == None:
            return ""
        else:
            return self.data_singleton.current_device.udid

    def get_current_device_model(self) -> str:
        if self.data_singleton.current_device == None:
            return ""
        else:
            return self.data_singleton.current_device.model

    def get_current_device_supported(self) -> bool:
        if self.data_singleton.current_device == None:
            return False
        else:
            return self.data_singleton.current_device.supported()

    def get_current_device_uses_bookrestore(self) -> bool:
        if self.data_singleton.current_device == None:
            return False
        else:
            return self.data_singleton.current_device.has_bookrestore()

    def get_current_device_patched(self) -> bool:
        if self.data_singleton.current_device == None:
            return True
        else:
            return self.data_singleton.current_device.is_exploit_fully_patched()

    def current_device_books_container_uuid_callback(self, uuid: Optional[str]=None) -> Optional[str | None]:
        # if there is no argument, return the existing uuid
        if uuid is None:
            return self.data_singleton.current_device.books_container_uuid
        self.data_singleton.current_device.books_container_uuid = uuid
        # save it to settings
        self.pref_manager.settings.setValue(
            f"{self.data_singleton.current_device.udid}_books_container_uuid", uuid
        )

    def get_app_hashes(self, bundle_ids: list[str]) -> dict:
        """
        Return app container identifiers ("hashes") for the requested bundle IDs.

        This is used by the Pocket Poster helper to fetch the PosterBoard container UUID.
        Connection issues (device unplugged / WiFi pairing drop) are converted into
        NuggetException so the GUI can display a friendly error instead of crashing.
        """
        if self.data_singleton.current_device is None or self.data_singleton.current_device.ld is None:
            raise NuggetException(
                QCoreApplication.translate("QCoreApplication", "No device connected."),
                QCoreApplication.translate(
                    "QCoreApplication",
                    "Refresh the device list and make sure your device is unlocked and trusted.",
                ),
            )

        try:
            apps = InstallationProxyService(lockdown=self.data_singleton.current_device.ld).get_apps(
                application_type="Any",
                calculate_sizes=False,
            )
        except Exception:
            raise NuggetException(
                QCoreApplication.translate(
                    "QCoreApplication",
                    "Failed to query installed apps from the device.",
                ),
                QCoreApplication.translate(
                    "QCoreApplication",
                    "Reconnect your device (or refresh the device list) and try again.",
                )
                + "\n\n"
                + traceback.format_exc(),
            )

        results: dict[str, str] = {}
        missing: list[str] = []

        for bundle_id in bundle_ids:
            app_info = apps.get(bundle_id)
            if not isinstance(app_info, dict):
                missing.append(bundle_id)
                continue

            container = app_info.get("Container")
            if not container:
                missing.append(bundle_id)
                continue

            results[bundle_id] = container.removeprefix(
                "/private/var/mobile/Containers/Data/Application/"
            )

        # PosterBoard is required for the helper to work.
        if "com.apple.PosterBoard" not in results:
            missing_txt = (
                "\n".join(missing)
                if missing
                else QCoreApplication.translate("QCoreApplication", "(unknown)")
            )
            raise NuggetException(
                QCoreApplication.translate(
                    "QCoreApplication",
                    "PosterBoard app hash was not found on this device.",
                ),
                QCoreApplication.translate(
                    "QCoreApplication", "Missing bundle IDs or containers:\n{0}"
                ).format(missing_txt),
            )

        return results

    def send_app_hashes_afc(self, hashes: dict) -> str:
        # create a temporary file to send it as
        with TemporaryDirectory() as tmpdir:
            # get the bundle id of Pocket Poster
            bundle_id = "com.leemin.Pocket-Poster"
            apps = InstallationProxyService(lockdown=self.data_singleton.current_device.ld).get_apps(application_type="User", calculate_sizes=False)
            for app in apps.values():
                if app["CFBundleExecutable"] == "Pocket Poster":
                    bundle_id = app["CFBundleIdentifier"]
                    break
                elif app["CFBundleExecutable"] == "LiveContainer":
                    # fallback for live container
                    bundle_id = app["CFBundleIdentifier"]
            afc = HouseArrestService(lockdown=self.data_singleton.current_device.ld, bundle_id=bundle_id, documents_only=True)
            # send each hash over
            for key in hashes.keys():
                fname = "Nugget" + key.replace("com.apple.", "") + "Hash"
                tmpf = os.path.join(tmpdir, fname)
                with open(tmpf, "w", encoding='UTF-8') as in_file:
                    in_file.write(hashes[key])
                afc.push(tmpf, f"/Documents/{fname}")
            return bundle_id

    def reset_device_pairing(self):
        # first, unpair it
        if self.data_singleton.current_device == None:
            return
        self.data_singleton.current_device.ld.unpair()
        # next, pair it again
        self.data_singleton.current_device.ld.pair()
        QMessageBox.information(
            None,
            QCoreApplication.translate("QCoreApplication", "Pairing Reset"),
            QCoreApplication.translate(
                "QCoreApplication",
                "Your device's pairing was successfully reset. Refresh the device list before applying.",
            ),
        )

    def add_skip_setup(self, files_to_restore: list[FileToRestore], restoring_domains: bool):
        """
        Add skip setup configuration files if enabled.

        This adds configuration files that skip the iOS setup wizard after restore.
        See devicemanagement/skip_setup.py for implementation details.
        """
        if self.pref_manager.skip_setup and (not self.get_current_device_supported() or restoring_domains):
            add_skip_setup_files(
                files_to_restore=files_to_restore,
                lockdown_client=self.data_singleton.current_device.ld,
                supervised=self.pref_manager.supervised,
                organization_name=self.pref_manager.organization_name,
            )

    def get_domain_for_path(
        self, path: str, owner: int = 501, use_bookrestore: bool = False
    ) -> tuple[str, str]:
        # returns (Path: str, Domain: str)
        if ((self.get_current_device_supported() and not path.startswith("/var/mobile/")) or (not self.data_singleton.current_device.has_partial_sparserestore() and self.get_current_device_uses_bookrestore() and use_bookrestore)) and not owner == 0:
            # don't do anything on sparserestore versions
            return path, ""
        fully_patched = not self.data_singleton.current_device.has_partial_sparserestore()
        # just make the Sys Containers to use the regular way (won't work for mga)
        sysSharedContainer = "SysSharedContainerDomain-"
        sysContainer = "SysContainerDomain-"
        if not fully_patched:
            sysSharedContainer += "."
            sysContainer += "."
        mappings: dict = {
            "/var/Managed Preferences/": "ManagedPreferencesDomain",
            "/var/root/": "RootDomain",
            "/var/preferences/": "SystemPreferencesDomain",
            "/var/MobileDevice/": "MobileDeviceDomain",
            "/var/mobile/": "HomeDomain",
            "/var/db/": "DatabaseDomain",
            "/var/containers/Shared/SystemGroup/": sysSharedContainer,
            "/var/containers/Data/SystemGroup/": sysContainer
        }
        for mapping in mappings.keys():
            if path.startswith(mapping):
                new_path = path.replace(mapping, "")
                new_domain = mappings[mapping]
                # if patched, include the next part of the path in the domain
                if fully_patched and (new_domain == sysSharedContainer or new_domain == sysContainer):
                    parts = new_path.split("/")
                    new_domain += parts[0]
                    new_path = new_path.replace(parts[0] + "/", "")
                return new_path, new_domain
        return path, ""

    def add_file_to_restore(
        self,
        contents: bytes,
        path: str,
        files_to_restore: list[FileToRestore],
        owner: int = 501,
        group: int = 501,
        use_bookrestore: bool = False,
    ):
        """
        Add a file to the restore list.

        Args:
            contents: File contents as bytes
            path: Target path on device
            files_to_restore: List to append the file to
            owner: File owner UID (default: 501 for mobile)
            group: File group GID (default: 501 for mobile)
            use_bookrestore: Whether to use BookRestore method
        """
        file_path, domain = self.get_domain_for_path(path, owner=owner, use_bookrestore=use_bookrestore)
        files_to_restore.append(FileToRestore(
            contents=contents,
            restore_path=file_path,
            domain=domain,
            owner=owner, group=group
        ))

    def _load_gestalt_plist(self):
        """Load the MobileGestalt plist from file or saved data."""
        if self.data_singleton.gestalt_path is None:
            return None

        if self.data_singleton.gestalt_path == self.data_singleton.SAVED_GESTALT_STRING:
            return self.pref_manager.get_mga_data(self.get_current_device_udid())

        with open(self.data_singleton.gestalt_path, "rb") as in_fp:
            return plistlib.load(in_fp)

    def _process_tweak(self, tweak, tweak_context: dict):
        """
        Process a single tweak and update the context.

        Args:
            tweak: The tweak instance to process
            tweak_context: Dictionary containing shared state:
                - gestalt_plist: MobileGestalt plist data
                - flag_plist: Feature flags plist
                - eligibility_files: Eligibility tweak files
                - ai_file: AI eligibility file
                - basic_plists: Basic plist tweaks
                - basic_plists_ownership: Plist ownership info
                - files_data: Raw file data
                - uses_domains: Whether tweaks use domains
                - use_bookrestore: Whether to use BookRestore
                - files_to_restore: Files list
                - tmp_dirs: Temporary directories list
                - update_label: Progress callback
        """
        if isinstance(tweak, FeatureFlagTweak):
            tweak_context["flag_plist"] = tweak.apply_tweak(tweak_context["flag_plist"])
            if getattr(tweak, "enabled", False):
                tweak_context["applied_groups"].add("Feature Flags")

        elif isinstance(tweak, EligibilityTweak):
            tweak_context["eligibility_files"] = tweak.apply_tweak()
            if getattr(tweak, "enabled", False):
                tweak_context["applied_groups"].add("Eligibility")

        elif isinstance(tweak, AITweak):
            tweak_context["ai_file"] = tweak.apply_tweak()
            if getattr(tweak, "enabled", False):
                tweak_context["applied_groups"].add("AI Enabler")

        elif isinstance(tweak, (BasicPlistTweak, RdarFixTweak, AdvancedPlistTweak)):
            tweak_context["basic_plists"] = tweak.apply_tweak(
                tweak_context["basic_plists"], self.pref_manager.allow_risky_tweaks
            )
            tweak_context["basic_plists_ownership"][tweak.file_location] = tweak.owner
            if getattr(tweak, "enabled", False):
                if isinstance(tweak, RdarFixTweak):
                    tweak_context["applied_groups"].add("RDAR Fix")
                else:
                    tweak_context["applied_groups"].add("Plist Tweaks")
            if tweak.enabled and isinstance(tweak, RdarFixTweak):
                if Version(self.get_current_device_version()) >= Version("26.0"):
                    tweak_context["use_bookrestore"] = True

        elif isinstance(tweak, NullifyFileTweak):
            tweak.apply_tweak(tweak_context["files_data"])
            if getattr(tweak, "enabled", False):
                tweak_context["applied_groups"].add("File Resets")
            if tweak.enabled and tweak.file_location.value.startswith("/var/mobile/"):
                tweak_context["uses_domains"] = True

        elif isinstance(tweak, (PosterboardTweak, TemplatesTweak)):
            tmp_dir = TemporaryDirectory()
            tweak_context["tmp_dirs"].append(tmp_dir)
            tweak.apply_tweak(
                files_to_restore=tweak_context["files_to_restore"],
                output_dir=fix_windows_path(tmp_dir.name),
                templates=tweaks[TweakID.Templates].templates,
                version=self.get_current_device_version(),
                update_label=tweak_context["update_label"],
            )
            if isinstance(tweak, PosterboardTweak):
                if tweak.uses_domains() or not tweak.is_empty():
                    tweak_context["applied_groups"].add("PosterBoard")
            else:
                if tweak.uses_domains() or not tweak.is_empty():
                    tweak_context["applied_groups"].add("Templates")
            if tweak.uses_domains():
                tweak_context["uses_domains"] = True
            elif not tweak.is_empty():
                tweak_context["use_bookrestore"] = True

        elif isinstance(tweak, StatusBarTweak):
            tweak.apply_tweak(files_to_restore=tweak_context["files_to_restore"])
            if tweak.enabled:
                tweak_context["uses_domains"] = True
                tweak_context["applied_groups"].add("Status Bar")

        else:
            # MobileGestalt tweaks
            if tweak_context["gestalt_plist"] is not None:
                tweak_context["gestalt_plist"] = tweak.apply_tweak(
                    tweak_context["gestalt_plist"]
                )
                if tweak.enabled:
                    tweak_context["use_bookrestore"] = True
                    tweak_context["applied_groups"].add("MobileGestalt")
            elif tweak.enabled:
                raise NuggetException(
                    QCoreApplication.translate(
                        "QCoreApplication",
                        "No mobilegestalt file provided! Please select your file to apply mobilegestalt tweaks.",
                    )
                )

    def _add_generated_files(self, tweak_context: dict):
        """
        Add all generated files to the restore list.

        Args:
            tweak_context: Context dictionary with processed tweak data
        """
        files_to_restore = tweak_context["files_to_restore"]
        use_bookrestore = tweak_context["use_bookrestore"]

        # Feature flags
        if len(tweak_context["flag_plist"]) > 0:
            self.concat_file(
                contents=plistlib.dumps(tweak_context["flag_plist"]),
                path=FileLocation.featureflags.value,
                files_to_restore=files_to_restore,
            )

        # Gestalt data
        if tweak_context["gestalt_plist"] is not None and use_bookrestore:
            gestalt_data = plistlib.dumps(tweak_context["gestalt_plist"])
            self.concat_file(
                contents=gestalt_data,
                path=FileLocation.mga.value,
                files_to_restore=files_to_restore,
                use_bookrestore=True,
            )

        # Eligibility files
        if tweak_context["eligibility_files"]:
            eligibility_files = tweak_context["eligibility_files"]
            if not self.get_current_device_supported():
                for file in eligibility_files:
                    self.concat_file(
                        contents=file.contents,
                        path=file.restore_path,
                        files_to_restore=files_to_restore,
                        use_bookrestore=use_bookrestore,
                    )
            else:
                files_to_restore.extend(eligibility_files)

        # AI eligibility file
        if tweak_context["ai_file"] is not None:
            self.concat_file(
                contents=tweak_context["ai_file"].contents,
                path=tweak_context["ai_file"].restore_path,
                files_to_restore=files_to_restore,
                use_bookrestore=use_bookrestore,
            )

        # Basic plists
        for location, plist in tweak_context["basic_plists"].items():
            ownership = tweak_context["basic_plists_ownership"].get(location, 501)
            self.concat_file(
                contents=plistlib.dumps(plist),
                path=location.value,
                files_to_restore=files_to_restore,
                owner=ownership,
                group=ownership,
                use_bookrestore=use_bookrestore,
            )

        # Raw file data
        for location, data in tweak_context["files_data"].items():
            ownership = data.owner if isinstance(data, NullifyFileTweak) else 501
            self.concat_file(
                contents=data,
                path=location.value,
                files_to_restore=files_to_restore,
                owner=ownership,
                group=ownership,
                use_bookrestore=use_bookrestore,
            )

    def _add_ssl_truststore(self, files_to_restore: list[FileToRestore]):
        """Add SSL TrustStore if enabled in preferences."""
        if self.pref_manager.restore_truststore:
            with open(get_bundle_files("files/SSLconf/TrustStore.sqlite3"), "rb") as f:
                certsDB = f.read()

            files_to_restore.append(
                FileToRestore(
                    contents=certsDB,
                    restore_path="trustd/private/TrustStore.sqlite3",
                    domain="ProtectedDomain",
                    owner=501,
                    group=501,
                    mode=_FileMode.S_IRUSR
                    | _FileMode.S_IWUSR
                    | _FileMode.S_IRGRP
                    | _FileMode.S_IWGRP
                    | _FileMode.S_IROTH
                    | _FileMode.S_IWOTH,
                )
            )

    ## APPLYING OR REMOVING TWEAKS AND RESTORING
    def start_restore(self, files_to_restore: list[FileToRestore], use_bookrestore: bool, update_label=lambda x: None):
        self.update_label = update_label
        self.do_not_unplug = ""
        if self.data_singleton.current_device.connected_via_usb:
            self.do_not_unplug = "\n" + QCoreApplication.translate(
                "QCoreApplication", "DO NOT UNPLUG"
            )
        restore_bookrestore = use_bookrestore and not self.data_singleton.current_device.has_partial_sparserestore()
        if restore_bookrestore:
            if self.pref_manager.bookrestore_apply_mode == BookRestoreApplyMethod.AFC:
                update_label(
                    QCoreApplication.translate(
                        "QCoreApplication", "Creating connection to device..."
                    )
                    + self.do_not_unplug
                )
                perform_bookrestore(files=files_to_restore, lockdown_client=self.data_singleton.current_device.ld, current_device_books_uuid_callback=self.current_device_books_container_uuid_callback, progress_callback=self.update_label, transfer_mode=self.pref_manager.bookrestore_transfer_mode)
            else:
                update_label(
                    QCoreApplication.translate(
                        "QCoreApplication", "Generating BookRestore database..."
                    )
                    + self.do_not_unplug
                )
                afc = AfcService(self.data_singleton.current_device.ld)
                if self.pref_manager.bookrestore_transfer_mode == BookRestoreFileTransferMethod.OnDevice:
                    # don't create a server, just add the file to the file list
                    db_path = os.path.join(br_files, "BLDatabaseManager.sqlite")
                    mga_file = [file for file in files_to_restore if file.restore_path.endswith("MobileGestalt.plist")][0]
                    _, filename = os.path.split(mga_file.restore_path)
                    afc.set_file_contents(filename, mga_file.contents)
                else:
                    server_folder = create_server_folder()
                    server_prefix = create_local_server()
                    db_path = os.path.join(server_folder, "tmp.BLDatabaseManager.sqlite")
                    generate_bldbmanager(files_to_restore, db_path, afc, server_prefix)
                # remove the files that dont have a domain from files
                files_to_restore = [file for file in files_to_restore if (file.domain != "" and file.domain != None)]
                # Add the dbs to the files to restore
                db_restore_path = "Documents/BLDatabaseManager/BLDatabaseManager.sqlite"
                db_restore_domain = "SysSharedContainerDomain-systemgroup.com.apple.media.shared.books"
                print(db_path)
                files_to_restore.append(FileToRestore(
                    contents=None, restore_path=db_restore_path,
                    contents_path=db_path,
                    domain=db_restore_domain
                ))
                files_to_restore.append(FileToRestore(
                    contents=None, restore_path=f"{db_restore_path}-shm",
                    contents_path=f"{db_path}-shm",
                    domain=db_restore_domain
                ))
                files_to_restore.append(FileToRestore(
                    contents=None, restore_path=f"{db_restore_path}-wal",
                    contents_path=f"{db_path}-shm",
                    domain=db_restore_domain
                ))
            msg = ""

        if not restore_bookrestore or self.pref_manager.bookrestore_apply_mode == BookRestoreApplyMethod.Restore:
            update_label(
                QCoreApplication.translate(
                    "QCoreApplication", "Preparing to restore..."
                )
                + self.do_not_unplug
            )
            restore_files(
                files=files_to_restore, reboot=self.pref_manager.auto_reboot,
                lockdown_client=self.data_singleton.current_device.ld,
                progress_callback=self.progress_callback
            )
            if restore_bookrestore:
                # wait for device reconnect and then reboot again after download (ie. specified timeout)
                update_label(
                    QCoreApplication.translate(
                        "QCoreApplication", "Waiting for device to reconnect..."
                    )
                    + "\n"
                    + QCoreApplication.translate(
                        "QCoreApplication", "Please complete the setup on your device."
                    )
                )
                max_timeout = time.time() + 180
                connected = False
                while not connected and max_timeout >= time.time():
                    try:
                        new_ld = create_using_usbmux(serial=self.get_current_device_udid(), pair_timeout=180)
                        connected = True
                    except (MuxException, ConnectionRefusedError, OSError):
                        # Device may not be ready yet, keep trying
                        time.sleep(1)
                cleanup_server_folder()
                if not connected:
                    raise NuggetException("Failed to reconnect to the device. Please reboot it manually after the restore.")
                update_label(
                    QCoreApplication.translate(
                        "QCoreApplication", "Waiting for changes to apply..."
                    )
                )
                time.sleep(20)
                update_label(
                    QCoreApplication.translate(
                        "QCoreApplication", "Rebooting to apply changes..."
                    )
                )
                cleanup_server_folder()
                reboot_device(reboot=True, lockdown_client=new_ld)
            msg = QCoreApplication.translate(
                "QCoreApplication",
                "Your device will now restart.\n\nRemember to turn Find My back on!",
            )
            if not self.pref_manager.auto_reboot:
                msg = QCoreApplication.translate(
                    "QCoreApplication", "Please restart your device to see changes."
                )
        return ApplyAlertMessage(
            txt=QCoreApplication.translate("QCoreApplication", "All done! ") + msg,
            title=QCoreApplication.translate("QCoreApplication", "Success!"),
            icon=QMessageBox.Icon.Information,
        )
    def progress_callback(self, progress: int):
        if self.update_label == None:
            return
        prog = ""
        if progress != None:
            prog = f" ({progress:6.1f}% )"
        self.update_label(
            QCoreApplication.translate(
                "QCoreApplication", "Restoring to device...{0}{1}"
            ).format(prog, self.do_not_unplug)
        )
    def apply_changes(self, update_label=lambda x: None, show_alert=lambda x: None):
        """
        Apply all enabled tweaks to the connected device.

        This method:
        1. Loads MobileGestalt plist if available
        2. Processes all enabled tweaks
        3. Generates restore files
        4. Restores files to device via Sparserestore or BookRestore

        Args:
            update_label: Callback for progress updates
            show_alert: Callback for displaying alerts
        """
        files_to_restore: list[FileToRestore] = []
        tmp_dirs = []

        try:
            update_label(
                QCoreApplication.translate(
                    "QCoreApplication", "Applying changes to files..."
                )
            )

            # Initialize tweak processing context
            tweak_context = {
                "gestalt_plist": self._load_gestalt_plist(),
                "flag_plist": {},
                "eligibility_files": None,
                "ai_file": None,
                "basic_plists": {},
                "basic_plists_ownership": {},
                "files_data": {},
                "uses_domains": False,
                "use_bookrestore": False,
                "applied_groups": set(),
                "files_to_restore": files_to_restore,
                "tmp_dirs": tmp_dirs,
                "update_label": update_label,
            }

            # Process all tweaks
            for tweak_name in tweaks:
                self._process_tweak(tweaks[tweak_name], tweak_context)

            # Apply custom gestalt tweaks
            if tweak_context["gestalt_plist"] is not None:
                tweak_context["gestalt_plist"] = CustomGestaltTweaks.apply_tweaks(
                    tweak_context["gestalt_plist"]
                )
                if len(CustomGestaltTweaks.custom_tweaks) > 0:
                    tweak_context["use_bookrestore"] = True

            # Generate backup
            update_label(
                QCoreApplication.translate("QCoreApplication", "Generating backup...")
            )

            # Add skip setup files
            should_skip_setup = tweak_context["uses_domains"] and (
                not tweak_context["use_bookrestore"]
                or self.pref_manager.bookrestore_apply_mode
                == BookRestoreApplyMethod.Restore
            )
            self.add_skip_setup(files_to_restore, should_skip_setup)

            # Add generated files to restore list
            self._add_generated_files(tweak_context)

            # Add SSL TrustStore if enabled
            if tweak_context["uses_domains"]:
                self._add_ssl_truststore(files_to_restore)

            # Restore to device
            final_alert = self.start_restore(
                files_to_restore, tweak_context["use_bookrestore"], update_label
            )
            try:
                groups = sorted(tweak_context.get("applied_groups", set()))
                if len(groups) > 0:
                    summary = "Applied groups:\n" + "\n".join(f"- {g}" for g in groups)
                else:
                    summary = "Applied groups:\n- (none)"
                summary += f"\n\nFiles to restore: {len(files_to_restore)}"
                if getattr(final_alert, "detailed_txt", None):
                    final_alert.detailed_txt = f"{final_alert.detailed_txt}\n\n{summary}"
                else:
                    final_alert.detailed_txt = summary
            except Exception:
                pass
            update_label(QCoreApplication.translate("QCoreApplication", "Success!"))

        except Exception as e:
            final_alert = show_apply_error(e, update_label, files_list=files_to_restore)

        finally:
            close_dl_connection()
            # Cleanup temporary directories
            for tmp_dir in tmp_dirs:
                try:
                    tmp_dir.cleanup()
                except Exception as e:
                    print(f"Cleanup error: {e}")
            show_alert(final_alert)

    ## RESETTING TWEAKS
    def reset_tweaks(self, reset_pages: list[Page], settings: QSettings, update_label=lambda x: None, show_alert=lambda x: None):
        try:
            # create the restore file list
            files_to_restore: list[FileToRestore] = []
            # Generate backup
            update_label(
                QCoreApplication.translate("QCoreApplication", "Generating backup...")
            )
            files_to_null: list[str] = []
            uses_domains = False
            use_bookrestore = False

            # use if-statements instead of match (switch) statements for compatibility with Python 3.9
            for page in reset_pages:
                if page == Page.Gestalt:
                    ## MOBILE GESTALT
                    # remove the saved device model, hardware, and cpu
                    settings.setValue(
                        f"{self.data_singleton.current_device.udid}_model", ""
                    )
                    settings.setValue(
                        f"{self.data_singleton.current_device.udid}_hardware", ""
                    )
                    settings.setValue(
                        f"{self.data_singleton.current_device.udid}_cpu", ""
                    )
                    files_to_null.append(FileLocation.mga.value)
                    if self.get_current_device_uses_bookrestore():
                        use_bookrestore = True
                elif page == Page.FeatureFlags:
                    ## FEATURE FLAGS
                    files_to_null.append(FileLocation.featureflags.value)
                elif page == Page.StatusBar:
                    ## STATUS BAR
                    files_to_restore.append(FileToRestore(
                        contents=b"",
                        restore_path="/Library/SpringBoard/statusBarOverrides",
                        domain="HomeDomain"
                    ))
                    uses_domains = True
                elif page == Page.Daemons:
                    ## DAEMONS
                    default_daemons = {
                        "com.apple.magicswitchd.companion": True,
                        "com.apple.security.otpaird": True,
                        "com.apple.dhcp6d": True,
                        "com.apple.bootpd": True,
                        "com.apple.ftp-proxy-embedded": False,
                        "com.apple.relevanced": True
                    }
                    self.concat_file(
                        contents=plistlib.dumps(default_daemons),
                        path=FileLocation.disabledDaemons.value,
                        files_to_restore=files_to_restore,
                        owner=0, group=0
                    )
                    uses_domains = True
                elif page == Page.RiskyTweaks:
                    ## RESOLUTION MODIFICATIONS
                    files_to_null.append(FileLocation.resolution.value)
                    if Version(self.get_current_device_version()) >= Version("26.0"):
                        use_bookrestore = True
                elif page == Page.Springboard:
                    ## SPRINGBOARD
                    files_to_null.append(FileLocation.springboard.value)
                    files_to_null.append(FileLocation.uikit.value)
                elif page == Page.InternalOptions:
                    ## INTERNAL OPTIONS
                    files_to_null.append(FileLocation.globalPreferences.value)
                    files_to_null.append(FileLocation.appStore.value)
                    files_to_null.append(FileLocation.backboardd.value)
                    files_to_null.append(FileLocation.coreMotion.value)
                    files_to_null.append(FileLocation.pasteboard.value)
                    files_to_null.append(FileLocation.notes.value)

            # add the files to null from the list
            for file_path in files_to_null:
                self.concat_file(
                    contents=b"",
                    path=file_path,
                    files_to_restore=files_to_restore,
                    use_bookrestore=use_bookrestore
                )

            if not use_bookrestore:
                self.add_skip_setup(files_to_restore, uses_domains)

            # restore to the device
            final_alert = self.start_restore(files_to_restore, use_bookrestore, update_label)
            update_label(QCoreApplication.translate("QCoreApplication", "Success!"))
        except Exception as e:
            final_alert = show_apply_error(e, update_label, files_list=files_to_restore)
        finally:
            show_alert(final_alert)
