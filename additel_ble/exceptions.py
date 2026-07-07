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
