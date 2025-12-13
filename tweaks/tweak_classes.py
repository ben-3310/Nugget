"""
Tweak classes for Nugget.

This module defines the base Tweak class and various specialized tweak types
for modifying iOS system files, including:
- BasicPlistTweak: Simple plist key modifications
- AdvancedPlistTweak: Multiple plist key modifications
- MobileGestaltTweak: MobileGestalt.plist modifications
- FeatureFlagTweak: iOS feature flag toggles
- NullifyFileTweak: File deletion/nullification
"""

import re
from typing import Any

from PySide6.QtCore import QCoreApplication

from exceptions.nugget_exception import NuggetException
from .basic_plist_locations import FileLocation


class Tweak:
    """
    Base class for all tweaks.

    Provides common functionality for enabling/disabling tweaks
    and storing key-value data.

    Attributes:
        key: The key/identifier for this tweak
        value: The value to apply
        owner: File owner UID (default: 501 for mobile user)
        group: File group GID (default: 501)
        enabled: Whether this tweak is active
    """

    def __init__(
            self,
            key: str | None = None,
            value: Any = 1,
            owner: int = 501, group: int = 501
        ):
        self.key = key
        self.value = value
        self.owner = owner
        self.group = group
        self.enabled = False

    def set_enabled(self, value: bool):
        """Enable or disable this tweak."""
        self.enabled = value

    def toggle_enabled(self):
        """Toggle the enabled state of this tweak."""
        self.enabled = not self.enabled

    def set_value(self, new_value: Any, toggle_enabled: bool = True):
        """Set the tweak value and optionally enable it."""
        self.value = new_value
        if toggle_enabled:
            self.enabled = True

    def apply_tweak(self):
        """Apply this tweak. Must be implemented by subclasses."""
        raise NotImplementedError

class NullifyFileTweak(Tweak):
    """
    Tweak that nullifies (empties) a file on the device.

    Used to reset or remove files by replacing them with empty content.
    """

    def __init__(
            self,
            file_location: FileLocation,
            owner: int = 501, group: int = 501
        ):
        super().__init__(key=None, value=None, owner=owner, group=group)
        self.file_location = file_location

    def apply_tweak(self, other_tweaks: dict):
        """Add this file to the nullify list if enabled."""
        if self.enabled:
            other_tweaks[self.file_location] = b""


class BasicPlistTweak(Tweak):
    """
    Tweak that modifies a single key in a plist file.

    Attributes:
        file_location: Target plist file location
        is_risky: Whether this tweak is considered risky (requires explicit permission)
    """

    def __init__(
            self,
            file_location: FileLocation,
            key: str | None,
            value: Any = True,
            owner: int = 501, group: int = 501,
            is_risky: bool = False
        ):
        super().__init__(key=key, value=value, owner=owner, group=group)
        self.file_location = file_location
        self.is_risky = is_risky

    def apply_tweak(self, other_tweaks: dict, risky_allowed: bool = False) -> dict:
        """Apply this plist modification if enabled and allowed."""
        if not self.enabled or (self.is_risky and not risky_allowed):
            return other_tweaks
        if self.key is None:
            raise ValueError("BasicPlistTweak requires a non-None key")
        if self.file_location in other_tweaks:
            other_tweaks[self.file_location][self.key] = self.value
        else:
            other_tweaks[self.file_location] = {self.key: self.value}
        return other_tweaks

class AdvancedPlistTweak(BasicPlistTweak):
    def __init__(
        self,
        file_location: FileLocation,
        keyValues: dict,
        owner: int = 501, group: int = 501,
        is_risky: bool = False
    ):
        super().__init__(file_location=file_location, key=None, value=keyValues, owner=owner, group=group, is_risky=is_risky)

    def set_multiple_values(self, keys: list[str], value: Any):
        for key in keys:
            self.value[key] = value

    def apply_tweak(self, other_tweaks: dict, risky_allowed: bool = False) -> dict:
        if not self.enabled or (self.is_risky and not risky_allowed):
            return other_tweaks
        plist = {}
        for key in self.value:
            plist[key] = self.value[key]
        other_tweaks[self.file_location] = plist
        return other_tweaks


class RdarFixTweak(BasicPlistTweak):
    def __init__(self):
        super().__init__(file_location=FileLocation.resolution, key=None)
        self.mode = 0
        self.di_type = -1

    def get_rdar_mode(self, model: str) -> int:
        if (model == "iPhone11,2" or model == "iPhone11,4" or model == "iPhone11,6"
            or model == "iPhone11,8"
            or model == "iPhone12,1" or model == "iPhone12,3" or model == "iPhone12,5"):
            self.mode = 1
        elif (model == "iPhone13,2" or model == "iPhone13,3" or model == "iPhone13,4"
              or model == "iPhone14,5" or model == "iPhone14,2" or model == "iPhone14,3"
              or model == "iPhone14,7" or model == "iPhone14,8" or model == "iPhone17,5"):
            self.mode = 2
        elif (model == "iPhone12,8" or model == "iPhone14,6"):
            self.mode = 3
        return self.mode

    def get_rdar_title(self) -> str:
        if self.mode == 1 or self.mode == 3:
            if self.di_type == -1:
                return QCoreApplication.tr("Revert RDAR fix")  # type: ignore
            return QCoreApplication.tr("RDAR Fix")  # type: ignore
        elif self.mode == 2:
            if self.di_type == -1:
                return QCoreApplication.tr("Revert Status Bar Fix")  # type: ignore
            return QCoreApplication.tr("Dynamic Island Status Bar Fix")  # type: ignore
        return "hide"

    def set_di_type(self, type: int):
        self.di_type = type

    def apply_tweak(self, other_tweaks: dict, risky_allowed: bool = False) -> dict:
        if not self.enabled:
            return other_tweaks
        if self.di_type == -1:
            # revert the fix
            other_tweaks[self.file_location] = {"nugget": 0} # data needed for revert to actually work
        elif self.mode == 1:
            # iPhone XR, XS, and 11
            plist = {
                "canvas_height": 1791,
                "canvas_width": 828
            }
            other_tweaks[self.file_location] = plist
        elif self.mode == 3:
            # iPhone SEs
            plist = {
                "canvas_height": 1779,
                "canvas_width": 1000
            }
            other_tweaks[self.file_location] = plist
        elif self.mode == 2:
            # Status bar fix (iPhone 12+)
            width = 2868
            height = 1320
            if self.di_type == 2556:
                width = 1179
                height = 2556
            elif self.di_type == 2796:
                width = 1290
                height = 2796
            elif self.di_type == 2622:
                width = 1206
                height = 2622
            elif self.di_type == 2868:
                width = 1320
                height = 2868
            elif self.di_type == 2736:
                width = 1260
                height = 2736
            plist = {
                "canvas_height": height,
                "canvas_width": width
            }
            other_tweaks[self.file_location] = plist
        return other_tweaks


class MobileGestaltTweak(Tweak):
    """
    Tweak that modifies MobileGestalt.plist values.

    MobileGestalt stores device capabilities and properties.
    Modifying it can enable/disable features like Dynamic Island, Boot Chime, etc.

    Attributes:
        subkey: Optional subkey for nested values
    """

    def __init__(
            self,
            key: str, subkey: str | None = None,
            value: Any = 1,
            owner: int = 501, group: int = 501
        ):
        super().__init__(key, value, owner, group)
        self.subkey = subkey

    def apply_tweak(self, plist: dict):
        """Apply this MobileGestalt modification."""
        if not self.enabled:
            return plist
        if self.key is None:
            raise ValueError("MobileGestaltTweak requires a non-None key")
        new_value = self.value
        if self.subkey is None:
            plist["CacheExtra"][self.key] = new_value
        else:
            plist["CacheExtra"][self.key][self.subkey] = new_value
        return plist

class MobileGestaltPickerTweak(Tweak):
    def __init__(
            self,
            key: str, subkey: str | None = None,
            values: list = [1]
        ):
        super().__init__(key=key, value=values)
        self.subkey = subkey
        self.selected_option = 0 # index of the selected option

    def apply_tweak(self, plist: dict):
        if not self.enabled or self.value[self.selected_option] == "Placeholder":
            return plist
        if self.key is None:
            raise ValueError("MobileGestaltPickerTweak requires a non-None key")
        new_value = self.value[self.selected_option]
        if self.subkey is None:
            plist["CacheExtra"][self.key] = new_value
        else:
            plist["CacheExtra"][self.key][self.subkey] = new_value
            if self.subkey == "ArtworkDeviceSubType":
                plist["CacheExtra"]["YlEtTtHlNesRBMal1CqRaA"] = 1
        return plist

    def set_selected_option(self, new_option: int, is_enabled: bool = True):
        self.selected_option = new_option
        self.enabled = is_enabled

    def get_selected_option(self) -> int:
        return self.selected_option

class MobileGestaltMultiTweak(Tweak):
    def __init__(self, keyValues: dict):
        super().__init__(key=None)
        self.keyValues = keyValues
        # key values looks like ["key name" = value]

    def apply_tweak(self, plist: dict):
        if not self.enabled:
            return plist
        for key in self.keyValues:
            plist["CacheExtra"][key] = self.keyValues[key]
        return plist

class MobileGestaltCacheDataTweak(Tweak):
    def __init__(self, slice_start: int, slice_length: int):
        super().__init__(key=None)
        self.slice_start = slice_start
        self.slice_len = slice_length

    def apply_tweak(self, plist: dict):
        if not self.enabled:
            return plist
        data = bytes(plist["CacheData"]).hex().lower()
        failed_str = QCoreApplication.tr("Failed to enable iPadOS:") + "\n"  # type: ignore
        if len(data) <= self.slice_start:
            raise NuggetException(failed_str + QCoreApplication.tr("CacheData is too short!"))  # type: ignore
        # skip the padding and get the last 2 bytes for every instance to find the offset
        pattern = re.compile(r"0+(?:5555)*([0-9a-f]{4})")
        offset = None
        value = None
        for match in pattern.finditer(data[self.slice_start : self.slice_start + self.slice_len]):
            value = match.group(1)
            if sum(c != "0" for c in value) >= 3:
                offset = self.slice_start + match.start(1)
                break

        # Error handling
        # Thanks Huy for the extra checks
        if offset is None:
            raise NuggetException(failed_str + QCoreApplication.tr("Pattern not found in CacheData."))  # type: ignore
        # Check the extrema offsets
        roffset = offset + 13
        loffset = offset - 67 # real
        if roffset >= len(data) - 1 or roffset - 1 < 0:
            raise NuggetException(
                failed_str + QCoreApplication.tr("Right offset out of range.")  # type: ignore
                + f'\nRight Offset: {roffset}, Data Length: {len(data)}'
            )
        if loffset <= 0 or loffset + 1 >= len(data):
            raise NuggetException(
                failed_str + QCoreApplication.tr("Left offset out of range.")  # type: ignore
                + f'\nLeft Offset: {loffset}, Data Length: {len(data)}'
            )

        for side_offset in [roffset, loffset]:
            offset_name = "Right" if side_offset == roffset else "Left"
            # check valid values
            if data[side_offset] not in ('1', '3'):
                err_msg: str = QCoreApplication.tr("Value at %SIDE offset is not 1 or 3.")  # type: ignore
                raise NuggetException(
                    failed_str + err_msg.replace("%SIDE", offset_name.lower())
                    + f'\nValue[{side_offset}] = {data[side_offset]}, Data Length: {len(data)}'
                )
            # check neighboring values
            if data[side_offset - 1] != '0' or data[side_offset + 1] != '0':
                err_msg: str = QCoreApplication.tr("Values of %SIDE offset neighbors are not 0.")  # type: ignore
                raise NuggetException(
                    failed_str + err_msg.replace("%SIDE", offset_name.lower())
                    + f'\nValue[{side_offset-1}] = {data[side_offset - 1]}, Value[{side_offset+1}] = {data[side_offset + 1]}, Data Length: {len(data)}'
                )

        # Set the value of the left offset to 3 to enable iPadOS
        data_list = list(data)
        data_list[loffset] = "3"
        data = "".join(data_list)
        plist["CacheData"] = bytes.fromhex(data)
        return plist



class FeatureFlagTweak(Tweak):
    """
    Tweak that toggles iOS feature flags.

    Feature flags control experimental or hidden iOS features.

    Attributes:
        flag_category: The category/domain for the flags (e.g., "SpringBoard")
        flag_names: List of flag names to toggle
        is_list: Whether flags should be set as dict with 'Enabled' key
        inverted: Whether to invert the enabled state
    """

    def __init__(
            self,
                flag_category: str, flag_names: list,
                is_list: bool=True, inverted: bool=False
            ):
        super().__init__(key=None)
        self.flag_category = flag_category
        self.flag_names = flag_names
        self.is_list = is_list
        self.inverted = inverted

    def apply_tweak(self, plist: dict):
        """Apply feature flag modifications."""
        to_enable = self.enabled
        if self.inverted:
            to_enable = not self.enabled
        # create the category list if it doesn't exist
        if not self.flag_category in plist:
            plist[self.flag_category] = {}
        for flag in self.flag_names:
            if self.is_list:
                plist[self.flag_category][flag] = {
                    'Enabled': to_enable
                }
            else:
                plist[self.flag_category][flag] = to_enable
        return plist
