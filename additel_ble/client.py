"""Asynchronous BLE client for Additel calibrators.

:class:`AdditelBLE` is the core of the library. It scans/connects, resolves the
GATT characteristics used for I/O (explicit override → documented UUIDs →
auto-discovery), performs the ``CODE?`` readiness handshake, buffers fragmented
notifications and exposes a simple ``query``/``write`` command API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Sequence, Tuple, Union

from bleak import BleakClient

from . import protocol
from .exceptions import (
    AdditelError,
    CharacteristicNotFoundError,
    CommandTimeoutError,
    ConnectionFailedError,
)
from .scanner import find_device

log = logging.getLogger(__name__)

GattRow = Tuple[str, str, List[str]]  # (service_uuid, char_uuid, properties)


class AdditelBLE:
    """Async client for an Additel BLE calibrator.

    Args:
        name: Advertised name to scan for (substring, case-insensitive).
            Ignored when ``address`` is given.
        address: Connect directly to this BLE address/UUID (skips scanning).
        notify_uuid: Force the notification characteristic UUID.
        write_uuid: Force the write characteristic UUID.
        handshake: Reply sent after the device's ``CODE?`` prompt to unlock
            communication (defaults to ``"@"``; pass ``None`` to disable).
        terminator: Command terminator (defaults to ``\\r\\n``).
        scan_timeout: Scan duration when discovering by name (seconds).
        command_timeout: Default per-command reply timeout (seconds).
        ready_timeout: How long to wait for the ``CODE?`` readiness signal.

    Example::

        async with AdditelBLE(name="ADT226") as dev:
            print(await dev.identify())
            print(await dev.query("CALibrator:MEASure:VALUE?"))
    """

    def __init__(
        self,
        name: str = "ADT226",
        address: Optional[str] = None,
        *,
        notify_uuid: Optional[str] = None,
        write_uuid: Optional[str] = None,
        handshake: Optional[str] = protocol.HANDSHAKE_TOKEN,
        terminator: str = protocol.DEFAULT_TERMINATOR,
        scan_timeout: float = 10.0,
        command_timeout: float = 3.0,
        ready_timeout: float = 5.0,
    ) -> None:
        self.name = name
        self.address = address
        self.override_notify = notify_uuid
        self.override_write = write_uuid
        # Handshake reply sent after the device's "CODE?" prompt (None to disable).
        self.handshake = handshake
        self.terminator = terminator
        self.scan_timeout = scan_timeout
        self.command_timeout = command_timeout
        self.ready_timeout = ready_timeout

        self._client: Optional[BleakClient] = None
        self._buffer = protocol.ResponseBuffer()
        self._lines: Optional["asyncio.Queue[str]"] = None
        self._notify_char = None
        self._write_char = None
        self._write_response = True
        self._ready = False

    # -- properties -------------------------------------------------------- #

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def ready(self) -> bool:
        """True if the device sent its ``CODE?`` readiness signal."""
        return self._ready

    @property
    def notify_uuid(self) -> Optional[str]:
        return str(self._notify_char.uuid) if self._notify_char else None

    @property
    def write_uuid(self) -> Optional[str]:
        return str(self._write_char.uuid) if self._write_char else None

    # -- connection -------------------------------------------------------- #

    async def connect(self) -> "AdditelBLE":
        """Scan (if needed), connect, resolve characteristics and go ready."""
        target: Union[str, object]
        if self.address is not None:
            target = self.address
        else:
            device = await find_device(self.name, timeout=self.scan_timeout)
            target = device
            self.address = getattr(device, "address", None)

        client = BleakClient(target)
        try:
            await client.connect()
        except Exception as exc:  # noqa: BLE001 - normalise to our exception type
            raise ConnectionFailedError(f"Failed to connect: {exc}") from exc
        if not client.is_connected:
            raise ConnectionFailedError("Client reported not connected.")

        self._client = client
        self._buffer.reset()
        self._lines = asyncio.Queue()
        self._resolve_characteristics()
        await client.start_notify(self._notify_char, self._on_notify)
        self._ready = await self._wait_ready()
        # The device unlocks command processing only after we answer its CODE?
        # prompt with the handshake token (within ~5s), so send it immediately.
        if self.handshake is not None:
            await self._send_handshake()
        return self

    async def disconnect(self) -> None:
        """Disconnect from the device (safe to call multiple times).

        We deliberately do **not** call ``stop_notify()`` here. ``disconnect()``
        tears notifications down on its own, and issuing an explicit CCCD write
        during teardown makes some devices (and macOS/CoreBluetooth) surface a
        spurious "Invalid Attribute Value Length" GATT error *after* the
        disconnect. This mirrors Additel's official example, which never calls
        ``stop_notify``.
        """
        client, self._client = self._client, None
        self._ready = False
        if client is None:
            return
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001 - best effort during teardown
            pass

    async def __aenter__(self) -> "AdditelBLE":
        return await self.connect()

    async def __aexit__(self, *exc_info) -> None:
        await self.disconnect()

    # -- characteristic resolution ---------------------------------------- #

    def gatt_table(self) -> List[GattRow]:
        """Return ``(service_uuid, char_uuid, properties)`` rows for the device.

        Handy for discovering the UUIDs of a specific model.
        """
        self._require_client()
        rows: List[GattRow] = []
        for service in self._client.services:
            for char in service.characteristics:
                rows.append((str(service.uuid), str(char.uuid), list(char.properties)))
        return rows

    def _get_char(self, uuid: Optional[str]):
        if not uuid:
            return None
        try:
            return self._client.services.get_characteristic(uuid)
        except Exception:  # noqa: BLE001 - bleak version differences
            return None

    def _first_char_with(self, props: Sequence[str]):
        for service in self._client.services:
            for char in service.characteristics:
                if any(p in char.properties for p in props):
                    return char
        return None

    def _pick_pinned(self, candidates: Sequence[Optional[str]], props: Sequence[str]):
        """First candidate UUID that exists and has one of ``props`` (no fallback)."""
        for uuid in candidates:
            char = self._get_char(uuid)
            if char is not None and any(p in char.properties for p in props):
                return char
            if uuid:
                log.warning("Requested UUID %s is missing or lacks %s.",
                            uuid, "/".join(props))
        return None

    def _first_char_with_all(self, props_a: Sequence[str], props_b: Sequence[str]):
        """First characteristic supporting both a ``props_a`` and a ``props_b`` property."""
        for service in self._client.services:
            for char in service.characteristics:
                if (any(p in char.properties for p in props_a)
                        and any(p in char.properties for p in props_b)):
                    return char
        return None

    def _resolve_characteristics(self) -> None:
        # 1) Explicit overrides / documented UUIDs win.
        notify = self._pick_pinned(
            [self.override_notify, protocol.DOC_NOTIFY_UUID], protocol.NOTIFY_PROPS
        )
        write = self._pick_pinned(
            [self.override_write, protocol.DOC_WRITE_UUID], protocol.WRITE_PROPS
        )

        # 2) Otherwise prefer a SINGLE characteristic that does both notify and
        #    write (the Additel UART pattern). This keeps command writes and reply
        #    notifications on the same characteristic, so replies actually come back
        #    — picking a stray writable characteristic instead means the command is
        #    written but the device never answers.
        if notify is None or write is None:
            combined = self._first_char_with_all(protocol.NOTIFY_PROPS, protocol.WRITE_PROPS)
            if combined is not None:
                notify = notify or combined
                write = write or combined

        # 3) Last resort: independent discovery.
        if notify is None:
            notify = self._first_char_with(protocol.NOTIFY_PROPS)
        if write is None:
            write = self._first_char_with(protocol.WRITE_PROPS)

        if notify is None:
            raise CharacteristicNotFoundError(
                "No characteristic with 'notify'/'indicate' found (cannot receive replies)."
            )
        if write is None:
            raise CharacteristicNotFoundError(
                "No characteristic with 'write' found (cannot send commands)."
            )
        self._notify_char = notify
        self._write_char = write
        # Prefer write-without-response whenever the characteristic supports it.
        # This matches Bleak's own default and Additel's official example; using
        # write-with-response on these characteristics makes the device reject the
        # write with ATT error 0x0D ("Invalid Attribute Value Length").
        self._write_response = "write-without-response" not in write.properties
        log.info("notify=%s  write=%s  props=[%s] -> %s", notify.uuid, write.uuid,
                 ", ".join(write.properties),
                 "with-response" if self._write_response else "without-response")

    # -- notifications ----------------------------------------------------- #

    def _on_notify(self, _sender, data: bytearray) -> None:
        log.debug("RX raw: %r", bytes(data))
        for line in self._buffer.feed(bytes(data)):
            log.debug("RX line: %s", line)
            if self._lines is not None:
                self._lines.put_nowait(line)

    async def _wait_ready(self) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.ready_timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                log.warning("No %r readiness signal received; continuing anyway.",
                            protocol.READY_TOKEN)
                return False
            try:
                line = await asyncio.wait_for(self._lines.get(), remaining)
            except asyncio.TimeoutError:
                return False
            if line.upper().startswith(protocol.READY_TOKEN):
                log.debug("device ready: %s", line)
                return True

    # -- command I/O ------------------------------------------------------- #

    def _require_client(self) -> None:
        if self._client is None:
            raise AdditelError("Not connected. Call connect() first.")

    async def _send_handshake(self) -> None:
        """Answer the device's ``CODE?`` prompt to unlock command processing.

        Per Additel's BLE protocol (ADT685 family — same UUIDs as the 226/227),
        after the gauge sends ``CODE?`` the client must send ``@\\r\\n`` within
        ~5 seconds, otherwise the device disconnects and never answers commands.
        """
        payload = protocol.build_command(self.handshake, terminator=self.terminator)
        log.debug("handshake TX: %r", payload)
        try:
            await self._client.write_gatt_char(
                self._write_char, payload, response=self._write_response
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("handshake write failed: %s", exc)
        # Discard any handshake acknowledgement so it isn't taken as a reply.
        if self._lines is not None:
            while not self._lines.empty():
                self._lines.get_nowait()

    async def write(self, command: str) -> None:
        """Send a command without waiting for a reply."""
        self._require_client()
        payload = protocol.build_command(command, terminator=self.terminator)
        log.debug("TX: %r", payload)
        await self._client.write_gatt_char(
            self._write_char, payload, response=self._write_response
        )

    async def query(self, command: str, *, timeout: Optional[float] = None) -> str:
        """Send a command and return the next reply line.

        Raises:
            CommandTimeoutError: if no reply arrives within the timeout.
        """
        self._require_client()
        # Drop stale/unsolicited lines so we return *this* command's reply.
        while not self._lines.empty():
            self._lines.get_nowait()
        await self.write(command)
        try:
            return await asyncio.wait_for(
                self._lines.get(), timeout if timeout is not None else self.command_timeout
            )
        except asyncio.TimeoutError:
            raise CommandTimeoutError(f"No reply to {command!r} within timeout.") from None

    # -- convenience ------------------------------------------------------- #

    async def identify(self) -> str:
        """Return the ``*IDN?`` identification string."""
        return await self.query("*IDN?")

    async def measure(self) -> str:
        """Return the current measured value (``CALibrator:MEASure:VALUE?``).

        Requires the device to be in Calibrator mode.
        """
        return await self.query("CALibrator:MEASure:VALUE?")
