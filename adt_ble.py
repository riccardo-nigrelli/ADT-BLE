#!/usr/bin/env python3
"""
ADT-BLE — BLE communication toolkit for Additel calibrators
===========================================================

Command-line tool to test Bluetooth Low Energy (BLE) communication with an
Additel ADT226 multifunction process calibrator (also works for the ADT227
and the ...Ex variants, and — with the right name/UUIDs — other Additel BLE
devices).

Cross-platform: runs on macOS, Windows and Linux thanks to the `bleak`
library (CoreBluetooth / WinRT / BlueZ under the hood — no code changes
needed between platforms).

What it does
------------
1. Scan for nearby BLE devices.
2. Match the calibrator by advertised name (or connect straight to an address).
3. Connect and resolve the GATT characteristics used for I/O:
   explicit overrides (--notify-uuid/--write-uuid) → Additel's documented
   UUIDs → automatic discovery from characteristic properties.
4. Subscribe to notifications and wait for the device's ``CODE?`` readiness
   signal.
5. Send SCPI commands (default: ``*IDN?`` and ``CALibrator:MEASure:VALUE?``)
   and print each reply.
6. Disconnect cleanly.

Transport details (Bleak, UUIDs, the ``CODE?`` handshake, the ``\\r\\n``
terminator) come from Additel's official reference material — see ``docs/``
and the links in ``README.md``.

Quick start
-----------
    python adt_ble.py                 # scan for "ADT226" and run the check
    python adt_ble.py --scan-only     # just list nearby BLE devices
    python adt_ble.py -v              # verbose: dump the GATT table (UUIDs)
    python adt_ble.py --address <MAC-or-UUID>
    python adt_ble.py --notify-uuid <UUID> --write-uuid <UUID>

Requires Python 3.8+ and the `bleak` package (see requirements.txt).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List, Optional, Sequence

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError
except ImportError:  # pragma: no cover - dependency hint
    sys.exit(
        "The 'bleak' package is required. Install it with:\n"
        "    python -m pip install -r requirements.txt"
    )

log = logging.getLogger("additel-bt")

# --------------------------------------------------------------------------- #
# Constants (from Additel's official BLE reference material)
# --------------------------------------------------------------------------- #

# Documented UUIDs. Additel notes these are for the ADT685 and "may differ"
# on other models, so they are only a *first guess* — the code falls back to
# automatic discovery when they are not present on the connected device.
DOC_SERVICE_UUID = "AF661820-D14A-4B21-90F8-54D58F8614F0"
DOC_NOTIFY_UUID = "1B6B9415-FF0D-47C2-9444-A5032F727B2D"
DOC_WRITE_UUID = "1B6B9415-FF0D-47C2-9444-A5032F727B2D"

# SCPI commands accept "\r\n", "\r", "\n" or "\0" as terminator; we send CRLF.
DEFAULT_TERMINATOR = "\r\n"

# Readiness signal the device emits once, right after we subscribe.
READY_TOKEN = "CODE"

# Default commands for a communication check:
#   *IDN?                       -> identity (serial, firmware, model)  [always works]
#   CALibrator:MEASure:VALUE?   -> current measured value (needs Calibrator mode)
DEFAULT_COMMANDS = ["*IDN?", "CALibrator:MEASure:VALUE?"]


# --------------------------------------------------------------------------- #
# Session wrapper around a connected BleakClient
# --------------------------------------------------------------------------- #

class AdditelSession:
    """Handles characteristic resolution, notification buffering and I/O."""

    def __init__(
        self,
        client: BleakClient,
        *,
        prefix: str = "",
        terminator: str = DEFAULT_TERMINATOR,
        notify_uuid: Optional[str] = None,
        write_uuid: Optional[str] = None,
    ) -> None:
        self.client = client
        self.prefix = prefix
        self.terminator = terminator
        self.override_notify = notify_uuid
        self.override_write = write_uuid

        self._rx_buffer = b""
        self._lines: "asyncio.Queue[str]" = asyncio.Queue()

        self.notify_char = None  # BleakGATTCharacteristic
        self.write_char = None   # BleakGATTCharacteristic
        self.write_response = True

    # -- GATT plumbing ----------------------------------------------------- #

    def dump_gatt(self) -> None:
        """Log the full GATT table (services + characteristics + properties).

        This is how you discover the UUIDs for a specific device model.
        """
        log.info("GATT table (services / characteristics / properties):")
        for service in self.client.services:
            log.info("  service %s  (%s)", service.uuid, service.description or "")
            for char in service.characteristics:
                log.info(
                    "    char %s  [%s]  (%s)",
                    char.uuid,
                    ", ".join(char.properties),
                    char.description or "",
                )

    def _get_char(self, uuid: Optional[str]):
        if not uuid:
            return None
        try:
            return self.client.services.get_characteristic(uuid)
        except Exception:  # noqa: BLE001 - bleak version differences
            return None

    def _first_char_with(self, wanted: Sequence[str]):
        for service in self.client.services:
            for char in service.characteristics:
                if any(prop in char.properties for prop in wanted):
                    return char
        return None

    def _pick(self, candidates, wanted_props, role):
        """Return the first usable characteristic, else auto-discover one."""
        for uuid in candidates:
            char = self._get_char(uuid)
            if char is not None and any(p in char.properties for p in wanted_props):
                return char
            if uuid:  # explicitly requested but not usable
                log.warning("Requested %s UUID %s is missing or lacks %s; "
                            "falling back to auto-discovery.",
                            role, uuid, "/".join(wanted_props))
        return self._first_char_with(wanted_props)

    def resolve_characteristics(self) -> None:
        """Pick the notify + write characteristics.

        Order of preference: explicit override → documented UUID → automatic
        discovery based on the characteristic's declared properties.
        """
        notify = self._pick(
            [self.override_notify, DOC_NOTIFY_UUID], ("notify", "indicate"), "notify"
        )
        write = self._pick(
            [self.override_write, DOC_WRITE_UUID],
            ("write", "write-without-response"),
            "write",
        )

        if notify is None:
            raise RuntimeError(
                "No characteristic with 'notify'/'indicate' found — cannot "
                "receive replies. Run with -v to inspect the GATT table."
            )
        if write is None:
            raise RuntimeError(
                "No characteristic with 'write' found — cannot send commands. "
                "Run with -v to inspect the GATT table."
            )

        self.notify_char = notify
        self.write_char = write
        # Use write-with-response only when the characteristic actually supports it.
        self.write_response = "write" in write.properties

        log.info("Notify characteristic: %s", notify.uuid)
        log.info(
            "Write  characteristic: %s (%s)",
            write.uuid,
            "with-response" if self.write_response else "without-response",
        )

    # -- notification handling --------------------------------------------- #

    def _on_notify(self, _sender, data: bytearray) -> None:
        """Accumulate bytes and split completed lines into the queue.

        BLE notifications can be fragmented, so we buffer until a terminator
        appears. All terminator variants are normalised to '\\n'.
        """
        self._rx_buffer += bytes(data)
        self._rx_buffer = (
            self._rx_buffer.replace(b"\r\n", b"\n")
            .replace(b"\r", b"\n")
            .replace(b"\x00", b"\n")
        )
        *complete, self._rx_buffer = self._rx_buffer.split(b"\n")
        for raw in complete:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                log.debug("RX line: %s", text)
                self._lines.put_nowait(text)

    async def start(self) -> None:
        self.resolve_characteristics()
        await self.client.start_notify(self.notify_char, self._on_notify)

    async def stop(self) -> None:
        if self.notify_char is not None:
            try:
                await self.client.stop_notify(self.notify_char)
            except Exception:  # noqa: BLE001 - best effort during teardown
                pass

    # -- command I/O ------------------------------------------------------- #

    async def wait_ready(self, timeout: float = 5.0) -> bool:
        """Wait for the device's ``CODE?`` readiness signal.

        Returns True if seen, False on timeout (the caller then continues anyway).
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            try:
                line = await asyncio.wait_for(self._lines.get(), remaining)
            except asyncio.TimeoutError:
                return False
            log.debug("startup line: %s", line)
            if line.upper().startswith(READY_TOKEN):
                return True

    async def send_and_wait(self, command: str, timeout: float = 3.0) -> Optional[str]:
        """Send one SCPI command and return the next reply line (or None)."""
        # Drop stale/unsolicited lines so we return *this* command's reply.
        while not self._lines.empty():
            self._lines.get_nowait()

        payload = f"{self.prefix}{command}{self.terminator}".encode("utf-8")
        log.debug("TX: %r", payload)
        await self.client.write_gatt_char(
            self.write_char, payload, response=self.write_response
        )
        try:
            return await asyncio.wait_for(self._lines.get(), timeout)
        except asyncio.TimeoutError:
            return None


# --------------------------------------------------------------------------- #
# Scan / connect / run
# --------------------------------------------------------------------------- #

async def scan_devices(scan_timeout: float):
    log.info("Scanning for BLE devices for %.0fs...", scan_timeout)
    return await BleakScanner.discover(timeout=scan_timeout)


def _log_device_list(devices) -> None:
    log.info("Discovered %d device(s):", len(devices))
    for dev in devices:
        log.info("  %-40s  %s", dev.address, dev.name or "<no name>")


async def find_device(name: str, scan_timeout: float, verbose: bool):
    """Return a BLEDevice matching `name`, or None if nothing matched."""
    devices = await scan_devices(scan_timeout)
    if verbose:
        _log_device_list(devices)

    matches = [d for d in devices if d.name and name.lower() in d.name.lower()]
    if not matches:
        log.error("No device matching '%s' found (%d devices seen). Is the "
                  "calibrator powered on with Bluetooth enabled and nearby?",
                  name, len(devices))
        return None
    if len(matches) > 1:
        log.warning("%d devices matched '%s'; using the first: %s",
                    len(matches), name, matches[0].address)
    chosen = matches[0]
    log.info("Found device: %s (%s)", chosen.name, chosen.address)
    return chosen


async def run_demo(args: argparse.Namespace) -> int:
    # --scan-only: just list what's around and exit (handy to find the name).
    if args.scan_only:
        devices = await scan_devices(args.scan_timeout)
        _log_device_list(devices)
        return 0

    if args.address:
        log.info("Using explicit address: %s", args.address)
        target = args.address
    else:
        target = await find_device(args.name, args.scan_timeout, args.verbose)
        if target is None:
            return 2

    log.info("Connecting...")
    async with BleakClient(target) as client:
        if not client.is_connected:
            log.error("Failed to connect.")
            return 3
        log.info("Connected.")

        session = AdditelSession(
            client,
            prefix="@" if args.at_prefix else "",
            notify_uuid=args.notify_uuid,
            write_uuid=args.write_uuid,
        )

        if args.verbose:
            session.dump_gatt()

        await session.start()

        if await session.wait_ready(timeout=args.ready_timeout):
            log.info("Device ready (received '%s?').", READY_TOKEN)
        else:
            log.warning("No '%s?' readiness signal received; continuing anyway.",
                        READY_TOKEN)

        for command in args.commands:
            reply = await session.send_and_wait(command, timeout=args.timeout)
            if reply is None:
                log.warning("%-32s -> (no reply within %.1fs)", command, args.timeout)
            else:
                log.info("%-32s -> %s", command, reply)

        await session.stop()

    log.info("Disconnected. Done.")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="adt_ble.py",
        description="Test BLE communication with an Additel calibrator (ADT226 by default).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--name", default="ADT226",
                        help="Advertised device name to match (substring, case-insensitive).")
    parser.add_argument("--address", default=None,
                        help="Connect directly to this BLE address (MAC on Windows/Linux, "
                             "UUID on macOS); skips the name scan.")
    parser.add_argument("--scan-only", action="store_true",
                        help="Only scan and list nearby BLE devices, then exit.")
    parser.add_argument("--scan-timeout", type=float, default=10.0,
                        help="How long to scan for the device (seconds).")
    parser.add_argument("--timeout", type=float, default=3.0,
                        help="Per-command reply timeout (seconds).")
    parser.add_argument("--ready-timeout", type=float, default=5.0,
                        help="How long to wait for the 'CODE?' readiness signal (seconds).")
    parser.add_argument("--commands", nargs="+", default=DEFAULT_COMMANDS, metavar="CMD",
                        help="SCPI commands to send (terminator added automatically).")
    parser.add_argument("--notify-uuid", default=None,
                        help="Override the notification characteristic UUID (see -v output).")
    parser.add_argument("--write-uuid", default=None,
                        help="Override the write characteristic UUID (see -v output).")
    parser.add_argument("--at-prefix", action="store_true",
                        help="Prefix each command with '@' (some firmware expects this).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output: dump the GATT table (UUIDs) and raw RX/TX.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return asyncio.run(run_demo(args))
    except BleakError as exc:
        log.error("Bluetooth error: %s", exc)
        return 4
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
