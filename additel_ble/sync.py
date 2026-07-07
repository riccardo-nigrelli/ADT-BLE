"""Synchronous facade over :class:`AdditelBLE` for non-async programs.

BLE is asynchronous by nature, but many programs are not. ``AdditelBLESync``
runs a private asyncio event loop in a background thread and marshals each
call onto it, so you get a plain blocking API while keeping a single, stateful
connection open across calls.

Example::

    from additel_ble import AdditelBLESync

    with AdditelBLESync(name="ADT226") as dev:
        print(dev.identify())
        print(dev.query("CALibrator:MEASure:VALUE?"))
"""

from __future__ import annotations

import asyncio
import threading
from typing import List, Optional

from .client import AdditelBLE, GattRow


class _LoopThread:
    """A dedicated asyncio event loop running in a daemon background thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        """Submit a coroutine to the loop and block until it completes."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if not self._loop.is_closed():
            self._loop.close()


class AdditelBLESync:
    """Blocking wrapper around :class:`AdditelBLE`. Same constructor arguments."""

    def __init__(self, *args, **kwargs) -> None:
        self._loop = _LoopThread()
        self._dev = AdditelBLE(*args, **kwargs)

    # connection
    def connect(self) -> "AdditelBLESync":
        self._loop.run(self._dev.connect())
        return self

    def disconnect(self) -> None:
        try:
            self._loop.run(self._dev.disconnect())
        finally:
            self._loop.close()

    def __enter__(self) -> "AdditelBLESync":
        return self.connect()

    def __exit__(self, *exc_info) -> None:
        self.disconnect()

    # I/O
    def write(self, command: str) -> None:
        self._loop.run(self._dev.write(command))

    def query(self, command: str, *, timeout: Optional[float] = None) -> str:
        return self._loop.run(self._dev.query(command, timeout=timeout))

    def identify(self) -> str:
        return self._loop.run(self._dev.identify())

    def measure(self) -> str:
        return self._loop.run(self._dev.measure())

    def gatt_table(self) -> List[GattRow]:
        return self._dev.gatt_table()

    # passthrough properties
    @property
    def is_connected(self) -> bool:
        return self._dev.is_connected

    @property
    def ready(self) -> bool:
        return self._dev.ready

    @property
    def address(self) -> Optional[str]:
        return self._dev.address

    @property
    def notify_uuid(self) -> Optional[str]:
        return self._dev.notify_uuid

    @property
    def write_uuid(self) -> Optional[str]:
        return self._dev.write_uuid


def scan_sync(timeout: float = 10.0):
    """Blocking device scan. Returns the list of discovered BLE devices."""
    from .scanner import scan

    loop = _LoopThread()
    try:
        return loop.run(scan(timeout))
    finally:
        loop.close()
