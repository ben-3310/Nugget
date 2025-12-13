import os
import sys
if os.name == 'nt':
    # only needed for windows
    import tempfile
    import subprocess

from enum import Enum

from .status_bar_c.status_setter import ffi
from exceptions.nugget_exception import NuggetException

class StatusBarItem(Enum):
    TimeStatusBarItem = 0
    DateStatusBarItem = 1
    QuietModeStatusBarItem = 2
    AirplaneModeStatusBarItem = 3
    CellularSignalStrengthStatusBarItem = 4
    SecondaryCellularSignalStrengthStatusBarItem = 5
    CellularServiceStatusBarItem = 6
    SecondaryCellularServiceStatusBarItem = 7
    # 8
    CellularDataNetworkStatusBarItem = 9
    SecondaryCellularDataNetworkStatusBarItem = 10
    # 11
    MainBatteryStatusBarItem = 12
    ProminentlyShowBatteryDetailStatusBarItem = 13
    # 14
    # 15
    BluetoothStatusBarItem = 16
    TTYStatusBarItem = 17
    AlarmStatusBarItem = 18
    # 19
    # 20
    LocationStatusBarItem = 21
    RotationLockStatusBarItem = 22
    CameraUseStatusBarItem = 23
    AirPlayStatusBarItem = 24
    AssistantStatusBarItem = 25
    CarPlayStatusBarItem = 26
    StudentStatusBarItem = 27
    MicrophoneUseStatusBarItem = 28
    VPNStatusBarItem = 29
    # 30
    PhonePickupStatusBarItem = 31
    # 32
    # 33
    # 34
    # 35
    # 36
    # 37
    # 38
    # 39
    LiquidDetectionStatusBarItem = 40
    VoiceControlStatusBarItem = 41
    # 42
    # 43
    Extra1StatusBarItem = 44
    # 45

class Setter:
    def __init__(self):
        self.current_overrides = ffi.new("StatusBarOverrideData *")
        self.silly_mode = False

    def apply_changes(self, new_overrides):
        self.current_overrides = new_overrides
    def get_overrides(self):
        return self.current_overrides

    def bool_array_to_str(self, arr: list[bool]) -> str:
        final_str = ""
        for a in arr:
            if a == 1:
                final_str += "1"
            else:
                final_str += "0"
        return final_str
    def get_data(self) -> bytes:
        overrides = self.current_overrides
        if self.silly_mode:
            # create a copy so that it doesn't change the original data
            overrides = ffi.new("StatusBarOverrideData *")
            # since it doesn't contain pointers, can just copy directly
            ffi.memmove(overrides, self.current_overrides, ffi.sizeof(self.current_overrides))
            # now turn on everything funny
            for i in range(46):
                if overrides.overrideItemIsEnabled[i] == 1:  # type: ignore
                    # don't change setting
                    continue
                overrides.overrideItemIsEnabled[i] = 1  # type: ignore
                overrides.values.itemIsEnabled[i] = 1  # type: ignore
        if os.name != 'nt':
            return bytes(ffi.buffer(self.current_overrides))  # type: ignore

        # --- PATH DETECTION START ---
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS  # type: ignore
            else:
                base_path = os.path.dirname(sys.executable)
                if not os.path.exists(os.path.join(base_path, "status_setter_windows.exe")):
                    if os.path.exists(os.path.join(base_path, "_internal", "status_setter_windows.exe")):
                        base_path = os.path.join(base_path, "_internal")
        else:
            base_path = os.getcwd()

        exe_path = os.path.join(base_path, "status_setter_windows.exe")
        # --- PATH DETECTION END ---

        # need to run the C++ cli tool because of differing bitfield standards
        tmpdir = tempfile.mkdtemp()
        tmpin = os.path.join(tmpdir, "sbin")
        tmpout = os.path.join(tmpdir, "status_bar_overrides")

        try:
            # generate the input file
            with open(tmpin, "w", encoding="utf-8") as in_file:
                for item in ([
                    self.bool_array_to_str(overrides.overrideItemIsEnabled),  # type: ignore
                    self.bool_array_to_str(overrides.values.itemIsEnabled),  # type: ignore
                    ffi.string(overrides.values.timeString).decode(),  # type: ignore
                    ffi.string(overrides.values.shortTimeString).decode(),  # type: ignore
                    ffi.string(overrides.values.dateString).decode(),  # type: ignore
                    ffi.string(overrides.values.serviceString).decode(),  # type: ignore
                    ffi.string(overrides.values.secondaryServiceString).decode(),  # type: ignore
                    ffi.string(overrides.values.serviceCrossfadeString).decode(),  # type: ignore
                    ffi.string(overrides.values.secondaryServiceCrossfadeString).decode(),  # type: ignore
                    ffi.string(overrides.values.batteryDetailString).decode(),  # type: ignore
                    ffi.string(overrides.values.primaryServiceBadgeString).decode(),  # type: ignore
                    ffi.string(overrides.values.secondaryServiceBadgeString).decode(),  # type: ignore
                    ffi.string(overrides.values.breadcrumbTitle).decode(),  # type: ignore
                    int(overrides.overrideTimeString),  # type: ignore
                    int(overrides.overrideDateString),  # type: ignore
                    int(overrides.overrideServiceString),  # type: ignore
                    int(overrides.overrideSecondaryServiceString),  # type: ignore
                    int(overrides.overrideBatteryDetailString),  # type: ignore
                    int(overrides.overridePrimaryServiceBadgeString),  # type: ignore
                    int(overrides.overrideSecondaryServiceBadgeString),  # type: ignore
                    int(overrides.overrideBreadcrumb),  # type: ignore
                    int(overrides.overrideDisplayRawWifiSignal),  # type: ignore
                    int(overrides.overrideDisplayRawGSMSignal),  # type: ignore
                    int(overrides.values.displayRawWifiSignal),  # type: ignore
                    int(overrides.values.displayRawGSMSignal),  # type: ignore
                    int(overrides.overrideDataNetworkType),  # type: ignore
                    int(overrides.values.dataNetworkType),  # type: ignore
                    int(overrides.overrideSecondaryDataNetworkType),  # type: ignore
                    int(overrides.values.secondaryDataNetworkType),  # type: ignore
                    int(overrides.overrideGSMSignalStrengthBars),  # type: ignore
                    int(overrides.values.GSMSignalStrengthBars),  # type: ignore
                    int(overrides.overrideSecondaryGSMSignalStrengthBars),  # type: ignore
                    int(overrides.values.secondaryGSMSignalStrengthBars),  # type: ignore
                    int(overrides.overrideBatteryCapacity),  # type: ignore
                    int(overrides.values.batteryCapacity),  # type: ignore
                    int(overrides.overrideWifiSignalStrengthBars),  # type: ignore
                    int(overrides.values.wifiSignalStrengthBars)  # type: ignore
                ]):
                    in_file.write(f"{item}\n")

            # --- FIX: Inject PATH env variable ---
            env = os.environ.copy()
            # Prepend our base_path to the PATH so the exe finds its DLLs first
            env["PATH"] = base_path + os.pathsep + env["PATH"]

            result = subprocess.run(
                [exe_path, tmpin, tmpout],
                encoding="utf-8",
                check=True,
                cwd=base_path,
                env=env  # <--- Critical for finding DLLs
            )
            print(f"returned {result}")

        except subprocess.CalledProcessError as e:
            # Enhanced Error Logging
            file_list = "Unable to list files"
            try:
                file_list = os.listdir(base_path)
            except:
                pass
            raise NuggetException(f"Failed to run status bar process.\nPath used: {base_path}\nFiles in path: {file_list}\nError: {e}")

        with open(tmpout, "rb") as in_file:
            contents = in_file.read()
        try:
            # clean up temporary files
            os.remove(tmpin)
            os.remove(tmpout)
            os.rmdir(tmpdir)
        except:
            pass
        return contents
