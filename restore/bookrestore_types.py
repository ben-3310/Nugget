from enum import Enum


class BookRestoreApplyMethod(Enum):
    AFC = 0
    Restore = 1


class BookRestoreFileTransferMethod(Enum):
    LocalHost = 0
    OnDevice = 1
