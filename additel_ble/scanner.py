"""BLE discovery helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from bleak import BleakScanner

from .exceptions import DeviceNotFoundError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bleak.backends.device import BLEDevice

log = logging.getLogger(__name__)


async def scan(timeout: float = 10.0) -> "List[BLEDevice]":
    """Scan for nearby BLE devices and return the list found."""
    log.debug("scanning for %.1fs", timeout)
    return await BleakScanner.discover(timeout=timeout)


async def find_device(name: str, *, timeout: float = 10.0) -> "BLEDevice":
    """Scan and return the first device whose advertised name contains ``name``.

    Matching is case-insensitive and substring-based.

    Raises:
        DeviceNotFoundError: if no advertised name matches.
    """
    if not name:
        raise ValueError("find_device() requires a non-empty name.")
    devices = await scan(timeout)
    matches = [d for d in devices if d.name and name.lower() in d.name.lower()]
    if not matches:
        raise DeviceNotFoundError(
            f"No BLE device matching {name!r} found ({len(devices)} device(s) seen). "
            "Is the calibrator powered on with Bluetooth enabled and nearby?"
        )
    if len(matches) > 1:
        log.warning("%d devices matched %r; using the first: %s",
                    len(matches), name, matches[0].address)
    return matches[0]
