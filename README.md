<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="ADT BLE" width="300">
  </picture>
</p>

<p align="center">
  <b>An integrable Python library for talking to Additel calibrators over Bluetooth Low Energy</b><br>
  <sub>+ a small test CLI &nbsp;·&nbsp; primary target <b>ADT226</b> (works with ADT227 and the <code>…Ex</code> variants)</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-64748b" alt="Platforms">
  <img src="https://img.shields.io/badge/BLE-Bleak-4f46e5?logo=bluetooth&logoColor=white" alt="Bleak">
  <img src="https://img.shields.io/badge/CLI-Typer-009485" alt="Typer">
  <img src="https://img.shields.io/badge/license-MIT-16a34a" alt="MIT">
</p>

---

**ADT-BLE** ships two things:

1. **`additel_ble`** — a clean, importable library with only one runtime dependency ([`bleak`](https://bleak.readthedocs.io)). It exposes an **async** client (`AdditelBLE`) and a **synchronous** facade (`AdditelBLESync`) for non-async programs.
2. **`adt-ble`** — a small **test CLI** (built with [Typer](https://typer.tiangolo.com) + [Rich](https://rich.readthedocs.io)), installed as an optional extra.

The library handles the fiddly parts of the Additel BLE protocol for you: connection, GATT characteristic resolution, the `CODE?` → `@` handshake, fragmented-notification reassembly, and automatic error-queue checking — behind a plain `query()` / `write()` API with typed exceptions.

> 📖 **Full documentation:** <https://riccardo-nigrelli.github.io/ADT-BLE/>
>
> ⚙️ **Cross-platform:** runs unchanged on macOS, Windows and Linux (Bleak uses CoreBluetooth / WinRT / BlueZ under the hood).

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [How it works](#how-it-works)
- [Library API](#library-api)
- [Reading values & why a command may not reply](#reading-values--why-a-command-may-not-reply)
- [CLI reference](#cli-reference)
- [Finding the device UUID](#finding-the-device-uuid)
- [Platform notes](#platform-notes)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)
- [References](#references)
- [License](#license)

## Features

- 📦 **Integrable library** — one runtime dependency (`bleak`), fully typed (`py.typed`).
- 🔀 **Async and sync APIs** — use `async/await` or a plain blocking interface.
- 🤝 **Automatic handshake** — replies `@` to the device's `CODE?` prompt so commands actually work.
- 🧩 **UUID auto-discovery** — finds the right characteristic even when it differs from the documented one.
- 🛑 **Automatic error checking** — reads `SYSTem:ERRor?` after each command and raises a typed error.
- 📥 **Robust framing** — reassembles fragmented BLE notifications up to the terminator.
- 🖥️ **Test CLI** — `scan`, `uuid`, `send`.

## Requirements

- **Python 3.8+**
- **Bluetooth** enabled on the host (a BLE adapter)
- The **Additel calibrator** powered on, Bluetooth enabled, within range (~20 m line-of-sight)

## Installation

As a library (to integrate into another program):

```bash
pip install .                                        # from a local clone
pip install "git+https://github.com/riccardo-nigrelli/ADT-BLE.git"
```

With the test CLI (the `cli` extra):

```bash
pip install ".[cli]"
```

Development environment (editable install + CLI + tests):

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt   # editable + cli + dev
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
</details>

## Quickstart

### Async (recommended)

```python
import asyncio
from additel_ble import AdditelBLE

async def main():
    async with AdditelBLE(name="ADT226") as dev:     # connect + handshake
        print("IDN:", await dev.identify())           # *IDN?
        print("Value:", await dev.measure())          # MEASure:CH? PV
        print("Unit:", await dev.query("CALibrator:MEASure:PRESsure:UNIT?"))

asyncio.run(main())
```

### Synchronous (non-async programs)

```python
from additel_ble import AdditelBLESync

with AdditelBLESync(name="ADT226") as dev:
    print(dev.identify())
    print(dev.measure())
```

### CLI

```bash
adt-ble scan                              # list nearby BLE devices
adt-ble send --name ADT226 "*IDN?"        # connect, send, disconnect
```

## How it works

- **Transport — UART over GATT.** Commands are written to a *write* characteristic; replies arrive as *notifications*.
- **Handshake.** Right after subscribing, the device sends `CODE?`. The client must answer `@\r\n` **within ~5 seconds**, or the device disconnects and ignores every command. `AdditelBLE` does this automatically (`handshake="@"`).
- **Characteristic resolution.** Explicit overrides → Additel's documented UUIDs → auto-discovery (a single characteristic that supports both *notify* and *write*).
- **Commands are SCPI strings** terminated with `\r\n`. Replies can be split across notifications, so they are buffered until the terminator.
- **Error checking.** With `check_errors=True` (default), after each command the library reads `SYSTem:ERRor?` and raises [`DeviceCommandError`](#exceptions) if the device queued a problem. The queue is cleared on connect and popped on each read, so the last error always resets.

Details: [`docs/additel_ble_notes.md`](docs/additel_ble_notes.md) · [`docs/scpi_commands.md`](docs/scpi_commands.md).

## Library API

### `AdditelBLE(name=None, address=None, *, notify_uuid=None, write_uuid=None, handshake="@", terminator="\r\n", scan_timeout=10.0, command_timeout=3.0, ready_timeout=5.0, check_errors=True)`

Asynchronous client. Provide **`name`** (scanned for) **or `address`** (connected to directly).

| Method / property | Description |
|---|---|
| `await connect()` → self | Scan (if needed), connect, resolve characteristics, handshake. |
| `await disconnect()` | Close the connection (idempotent). |
| `async with ...` | `connect()` / `disconnect()` automatically. |
| `await query(cmd, *, timeout=None, check_error=None)` → `str` | Send a command and return the reply line. |
| `await write(cmd, *, check_error=None)` | Send a command without waiting for a reply. |
| `await identify()` → `str` | Shortcut for `*IDN?`. |
| `await measure()` → `str` | Shortcut for `MEASure:CH? PV` (present value). |
| `await error()` → `str` | Read the device error queue (`SYSTem:ERRor?`). |
| `gatt_table()` → `list[GattEntry]` | The device's GATT table (for UUID discovery). |
| `is_connected`, `ready`, `address`, `notify_uuid`, `write_uuid` | State properties. |

`query()` raises `CommandTimeoutError` on no reply, or `DeviceCommandError` when the device flags an error.

### `AdditelBLESync(...)`

Same constructor and methods as `AdditelBLE`, but **blocking** (it runs an event loop on a background thread). Supports `with`.

### Functions & types

- `await scan(timeout=10.0)` / `scan_sync(timeout=10.0)` — list nearby BLE devices.
- `await find_device(name, *, timeout=10.0)` — first device matching `name` (raises `DeviceNotFoundError`).
- `GattEntry(service, characteristic, properties)` — a named tuple returned by `gatt_table()`.
- `ResponseBuffer`, `build_command(...)`, `parse_error(...)` — reusable protocol primitives.

### Exceptions

All inherit from `AdditelError`:

| Exception | Raised when |
|---|---|
| `DeviceNotFoundError` | No BLE device matched the name during a scan. |
| `ConnectionFailedError` | The BLE connection could not be established. |
| `CharacteristicNotFoundError` | No usable notify/write characteristic was found. |
| `CommandTimeoutError` | No reply arrived within the timeout. |
| `DeviceCommandError` | The device queued an error (`.code`, `.message`). |

## Reading values & why a command may not reply

`*IDN?` is an IEEE 488.2 common command: no parameter, no mode, it always answers. Most other commands don't answer unless used correctly:

- **Missing parameter.** To read the measured value use **`MEASure:CH? PV`** (note the `PV` parameter, separated by a space) — this is what `measure()` sends. `MEASure:CH?` alone returns nothing.
- **Wrong mode.** `CALibrator:...` commands only reply in **Calibrator mode**; others depend on the active function.
- **Set commands** (e.g. `...:UNIT <id>`) legitimately return nothing.

When a command is invalid in the current context the device stays silent but **queues an error**. With error checking on (default), the library reads it for you and raises `DeviceCommandError`. To inspect it manually:

```python
print(await dev.error())   # e.g. '-109,"Missing parameter"' or '0,"No error"'
```

Mode-independent commands that always reply (good for a smoke test): `SYSTem:VERSion?`, `SYSTem:DATE?`, `SYSTem:BLUEtooth:NAMe`, `SYSTem:BATTery:CAPacity?`.

## CLI reference

```bash
adt-ble --help
adt-ble scan [--name TEXT] [--timeout N]                     # list devices
adt-ble uuid <NAME> [--all]                                  # address/UUID for a name
adt-ble send [COMMANDS...] (--name TEXT | --uuid ADDR) [options]
```

`send` connects (by `--name` or `--address/--uuid`), sends the command(s) on one connection, prints each reply, then disconnects. With no command it sends `*IDN?`.

```bash
adt-ble send --name ADT226 "*IDN?"
adt-ble send --uuid AA:BB:CC:DD:EE:FF "*IDN?" "MEASure:CH? PV"   # several commands, one connection
adt-ble send -n ADT226 -v "*IDN?"                                # -v: GATT table + debug logs
adt-ble send -n ADT226 --no-error-check "SYSTem:VERSion?"        # skip the SYSTem:ERRor? check
```

Also runnable as `python -m additel_ble.cli ...`.

## Finding the device UUID

`adt-ble uuid <NAME>` prints the device address to pass to `send --uuid` (a system UUID on macOS, a MAC address on Windows/Linux):

```bash
adt-ble scan                 # see which names are advertised
adt-ble uuid ADT226          # -> Additel 226  →  AA:BB:CC:DD:EE:FF
```

To inspect the **GATT characteristic UUIDs** (rarely needed — auto-discovery handles them), run `adt-ble send -n ADT226 -v`: the verbose output prints the full GATT table and the characteristics it selected. To pin them explicitly, pass `notify_uuid=` / `write_uuid=` to `AdditelBLE`.

## Platform notes

| OS | Notes |
|---|---|
| **macOS** | Grant the terminal/IDE the **Bluetooth** permission on first run (*System Settings → Privacy & Security → Bluetooth*). Addresses are system-assigned **UUIDs**. |
| **Windows** | Requires **Windows 10 (build 16299+) / 11**, Bluetooth on. Addresses are **MAC**. |
| **Linux** | Requires **BlueZ ≥ 5.43** and the `bluetooth` service running. Addresses are **MAC**. |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No BLE device matching '…' found` | Device off/out of range; Bluetooth off; (macOS) permission not granted. Try `adt-ble scan`. |
| Connects, but every command times out | The handshake is off — keep `handshake="@"` (default). Check the `ready` state with `-v`. |
| A specific command returns no reply | Missing parameter or wrong mode — read `dev.error()` / append `SYSTem:ERRor?`. See [above](#reading-values--why-a-command-may-not-reply). |
| `DeviceCommandError: … -109 …` | The device reported a command error (here: missing parameter). |
| Auto-discovery picks the wrong characteristic | Pass `notify_uuid=` / `write_uuid=` from the `-v` GATT table. |

## Project layout

```
ADT-BLE/
├── additel_ble/              # the library (import: additel_ble)
│   ├── client.py             # AdditelBLE (async core)
│   ├── sync.py               # AdditelBLESync (sync facade)
│   ├── scanner.py            # scan / find_device
│   ├── protocol.py           # constants, ResponseBuffer, build_command, parse_error
│   ├── exceptions.py         # exception hierarchy
│   ├── cli.py                # Typer test CLI (adt-ble)
│   └── py.typed
├── examples/                 # async_usage.py, sync_usage.py
├── tests/                    # pytest suite
├── docs/                     # documentation site + protocol notes & references
├── assets/                   # logo
├── pyproject.toml
└── requirements.txt
```

## References

- Additel — *Device Communication* examples: <https://github.com/Additel-Code/Additel-Device-Communication>
- Additel — *Bluetooth Protocol for the ADT685* (same UUIDs & handshake as the 226/227): [`docs/additel_bluetooth_protocol_685.pdf`](docs/additel_bluetooth_protocol_685.pdf)
- Additel — *Programming Commands for 226 and 227*: <https://additel.com/download/programming_commands/226%20227/Programming%20Commands%20for%20226%20and%20227.pdf>
- [Bleak](https://bleak.readthedocs.io) · [Typer](https://typer.tiangolo.com) · [Rich](https://rich.readthedocs.io)

## License

Released under the [MIT License](LICENSE).
