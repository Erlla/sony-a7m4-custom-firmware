"""Known connection stops before a camera reader or writer is started."""


class ConnectionStop(RuntimeError):
    def __init__(self, message, reason, detail=None):
        self.reason = reason
        self.detail = detail or {}
        super().__init__(message)


class UnsupportedFirmwareError(ConnectionStop):
    def __init__(self, detail):
        super().__init__('当前相机固件非6.02版本', 'UNSUPPORTED_FIRMWARE', detail)
