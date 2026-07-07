"""Wire-level protocol details for Additel BLE devices.

This module has **no BLE dependency** — it holds the constants and the pure
response-reassembly logic, so it can be unit-tested and reused in isolation.
"""

from __future__ import annotations

from typing import List, Tuple

# --------------------------------------------------------------------------- #
# Documented UUIDs (from Additel's official BLE reference).
#
# Additel notes these are for the ADT685 and "may differ" on other models, so
# they are only a first guess — AdditelBLE falls back to auto-discovery based
# on characteristic properties when they are not present on the device.
# --------------------------------------------------------------------------- #
DOC_SERVICE_UUID = "AF661820-D14A-4B21-90F8-54D58F8614F0"
DOC_NOTIFY_UUID = "1B6B9415-FF0D-47C2-9444-A5032F727B2D"
DOC_WRITE_UUID = "1B6B9415-FF0D-47C2-9444-A5032F727B2D"

#: Terminator appended to every command (device also accepts "\r", "\n", "\0").
DEFAULT_TERMINATOR = "\r\n"

#: Readiness token the device emits once, right after notifications start.
#: Per Additel's BLE protocol (ADT685 family — same UUIDs as the 226/227), the
#: gauge sends "CODE?" and the client must reply with the handshake token below
#: within 5 seconds, otherwise the device disconnects and ignores all commands.
READY_TOKEN = "CODE"

#: Handshake reply the client must send after receiving "CODE?".
HANDSHAKE_TOKEN = "@"

#: GATT characteristic properties used to auto-discover the I/O characteristics.
NOTIFY_PROPS = ("notify", "indicate")
WRITE_PROPS = ("write", "write-without-response")


def build_command(
    command: str, *, prefix: str = "", terminator: str = DEFAULT_TERMINATOR
) -> bytes:
    """Encode an SCPI command to the bytes to write to the device."""
    return f"{prefix}{command}{terminator}".encode("utf-8")


def parse_error(response: str) -> Tuple[int, str]:
    """Parse a ``SYSTem:ERRor?`` reply into ``(code, message)``.

    The device answers in SCPI form ``<code>,"<message>"`` where code ``0`` means
    "No error". Unrecognised formats yield ``(0, <raw>)`` so callers never raise a
    false error on a parsing quirk.
    """
    text = response.strip()
    if not text:
        return 0, ""
    head, _, tail = text.partition(",")
    try:
        code = int(head.strip())
    except ValueError:
        return 0, text
    return code, tail.strip().strip('"')


class ResponseBuffer:
    """Reassembles fragmented BLE notifications into complete text lines.

    BLE notifications can split a reply across several packets, so bytes are
    buffered until a terminator appears. All terminator variants
    (``\\r\\n``, ``\\r``, ``\\n``, ``\\0``) are recognised.

    Usage::

        buf = ResponseBuffer()
        for chunk in incoming_notifications:
            for line in buf.feed(chunk):
                handle(line)
    """

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, data: bytes) -> List[str]:
        """Add received bytes; return the list of newly-completed lines."""
        self._buf += bytes(data)
        self._buf = (
            self._buf.replace(b"\r\n", b"\n")
            .replace(b"\r", b"\n")
            .replace(b"\x00", b"\n")
        )
        *complete, self._buf = self._buf.split(b"\n")
        lines: List[str] = []
        for raw in complete:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                lines.append(text)
        return lines

    def reset(self) -> None:
        """Discard any partially-buffered bytes."""
        self._buf = b""
