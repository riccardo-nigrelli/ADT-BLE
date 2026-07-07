"""
Additel-BLE — integrable Python library for BLE communication with Additel calibrators.

Public API
----------
Async (recommended)::

    import asyncio
    from additel_ble import AdditelBLE

    async def main():
        async with AdditelBLE(name="ADT226") as dev:
            print(await dev.identify())
            print(await dev.query("CALibrator:MEASure:VALUE?"))

    asyncio.run(main())

Synchronous (for non-async programs)::

    from additel_ble import AdditelBLESync

    with AdditelBLESync(name="ADT226") as dev:
        print(dev.identify())

See the project README for details on how the transport works and how to
discover the device UUIDs.
"""

from __future__ import annotations

import logging

from .client import AdditelBLE
from .exceptions import (
    AdditelError,
    CharacteristicNotFoundError,
    CommandTimeoutError,
    ConnectionFailedError,
    DeviceNotFoundError,
)
from .protocol import (
    DEFAULT_TERMINATOR,
    DOC_NOTIFY_UUID,
    DOC_SERVICE_UUID,
    DOC_WRITE_UUID,
    READY_TOKEN,
    ResponseBuffer,
    build_command,
)
from .scanner import find_device, scan
from .sync import AdditelBLESync, scan_sync

__version__ = "0.1.0"

# A library should never configure logging handlers itself; attach a NullHandler
# so "No handlers could be found" warnings never appear for consumers.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "AdditelBLE",
    "AdditelBLESync",
    "scan",
    "scan_sync",
    "find_device",
    "ResponseBuffer",
    "build_command",
    "AdditelError",
    "DeviceNotFoundError",
    "ConnectionFailedError",
    "CharacteristicNotFoundError",
    "CommandTimeoutError",
    "DEFAULT_TERMINATOR",
    "READY_TOKEN",
    "DOC_SERVICE_UUID",
    "DOC_NOTIFY_UUID",
    "DOC_WRITE_UUID",
    "__version__",
]
