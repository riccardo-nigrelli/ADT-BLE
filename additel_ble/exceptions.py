"""Exception hierarchy for the additel_ble library.

All library-specific errors derive from :class:`AdditelError`, so integrators
can catch everything with a single ``except AdditelError``.
"""

from __future__ import annotations


class AdditelError(Exception):
    """Base class for all additel_ble errors."""


class DeviceNotFoundError(AdditelError):
    """No BLE device matched the requested name during a scan."""


class ConnectionFailedError(AdditelError):
    """The BLE connection could not be established."""


class CharacteristicNotFoundError(AdditelError):
    """A required GATT characteristic (notify or write) was not found."""


class CommandTimeoutError(AdditelError):
    """No reply was received for a command within the timeout."""


class DeviceCommandError(AdditelError):
    """The device flagged an error in its queue after a command.

    Attributes:
        command: the command that triggered the error.
        code: the SCPI error code (0 means no error).
        message: the device's error description.
    """

    def __init__(self, command: str, code: int, message: str = "") -> None:
        self.command = command
        self.code = code
        self.message = message
        detail = f": {message}" if message else ""
        super().__init__(f"{command!r} -> device error {code}{detail}")
