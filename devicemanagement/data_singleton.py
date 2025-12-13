from pathlib import Path
from typing import Optional

from devicemanagement.constants import Device, Tweak

class DataSingleton:
    def __init__(self):
        self.current_device: Optional[Device] = None
        self.device_available: bool = False
        self.gestalt_path: Optional[str] = None
        self.SAVED_GESTALT_STRING = "Nugget Saved MobileGestalt File" # string for when the data is saved by Nugget
