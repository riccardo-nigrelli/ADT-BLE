# Technical notes — Additel BLE communication

How Bluetooth Low Energy communication with Additel calibrators (the 226/227
family and relatives) works, distilled from Additel's official material. See the
attached files in this folder and the links in the [README](../README.md).

## Communication model

Recent Additel devices expose a **UART-over-GATT** interface: you write a text
command to one characteristic and receive replies as **notifications** on
another (often the *same* one).

Steps, based on Additel's official example (Python + [Bleak](https://bleak.readthedocs.io),
a **cross-platform** library: macOS / Windows / Linux):

1. **Scan** for nearby BLE devices.
2. **Match by advertised name** (e.g. `ADT685`; for our model, `ADT226`).
3. **Connect** with `BleakClient`.
4. **Subscribe** to the *notification characteristic* to receive replies
   (delivered as `bytearray`).
5. **Handshake**: the device spontaneously sends **`CODE?`**; the client **must
   reply `@\r\n` within ~5 seconds**, otherwise the device closes the connection
   and **ignores every command**. Only after the handshake does it answer.
   (Documented in *Bluetooth Protocol for the ADT685*, which uses the same UUIDs
   as the 226/227.)
6. **Write** the command to the *write characteristic* as UTF-8 `bytes`.
7. Replies arrive in the notification callback.

> ⚠️ The generic 226 BLE guide claims you can "start sending commands" after
> `CODE?` **without replying** — that is **wrong/incomplete**: without the `@`
> handshake the 226 does not answer and disconnects after ~5s.

## UUIDs

> ⚠️ Additel states these UUIDs are for the **ADT685** and **may differ** on
> other models. The library therefore tries them first and, if absent, falls
> back to **auto-discovery** based on characteristic properties (`notify`/
> `indicate` to read, `write`/`write-without-response` to send).

| Role | UUID (ADT685 — starting point) |
|------|--------------------------------|
| Communication service | `AF661820-D14A-4B21-90F8-54D58F8614F0` |
| Notification characteristic | `1B6B9415-FF0D-47C2-9444-A5032F727B2D` |
| Write characteristic | `1B6B9415-FF0D-47C2-9444-A5032F727B2D` |

To discover the real UUIDs of your device, run `adt-ble send -n ADT226 -v` (CLI)
or call `AdditelBLE.gatt_table()`: you get the full GATT table (services +
characteristics with their properties) and the characteristics chosen for
notify/write.

## Command format (SCPI)

- Commands are SCPI strings (see [`scpi_commands.md`](scpi_commands.md) and
  [`226_227_commands.txt`](226_227_commands.txt)).
- **Terminator**: one of `\r\n`, `\r`, `\n`, `\0`. The library uses `\r\n`.
- **Structure**: *mnemonic* + space + *parameter* (e.g. `MEASure:CH? PV`).
- Parts in `[]` in the mnemonic are optional.
- **Write mode**: the characteristic is written with *write-without-response*
  when it supports it (matching Bleak's default and Additel's example); using
  write-with-response makes the device reject the write with ATT error `0x0D`.
- The `@` is **not** a per-command prefix — it is the **one-time handshake**
  token in reply to `CODE?` (see step 5). The library sends it automatically.
- BLE replies may arrive **fragmented** across notifications; they are buffered
  until the terminator.

## Error queue

When a command is invalid in the current context, the device usually stays
silent and pushes an error onto its queue instead. Read (and pop) it with
**`SYSTem:ERRor?`** — it returns `<code>,"<message>"`, where code `0` means
"No error". `*CLS` clears the whole queue. The library reads the queue after
each command (`check_errors=True`) and raises `DeviceCommandError` on a non-zero
code. Common codes: `-109` missing parameter, `-108` parameter not allowed,
`-110` command header error, `222` failed to read measure value.

## Useful commands

| Command | Description |
|---------|-------------|
| `*IDN?` | Identity: serial, firmware, model. Always replies. |
| `*CLS` / `*RST` | Clear registers / reset. |
| `MEASure:CH? PV` | Read the present value of the active measure channel. |
| `CALibrator:MEASure:VALUE?` | Read the measured value (Calibrator mode only). |
| `CALibrator:MEASure:PRESsure:UNIT?` | Read the external pressure-module unit. |
| `SYSTem:ERRor?` | Read the next error from the queue. |
| `SYSTem:VERSion?` | Firmware/hardware versions. |

The complete list (measurement, output, HART, thermal calculation, etc.) is in
[`226_227_commands.txt`](226_227_commands.txt).

## Reference files in this folder

- [`scpi_commands.md`](scpi_commands.md) — curated SCPI reference.
- [`226_227_commands.txt`](226_227_commands.txt) — full 226/227 command set (from the official PDF).
- [`additel_bluetooth_protocol_685.pdf`](additel_bluetooth_protocol_685.pdf) — official BLE protocol (handshake + UUIDs).
- [`additel_official_bluetooth_guide.md`](additel_official_bluetooth_guide.md) — Additel's official BLE guide (copy).
- [`additel_official_bluetooth_example.py`](additel_official_bluetooth_example.py) — Additel's official Python example (copy).
