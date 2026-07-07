# SCPI command reference (ADT226 / ADT227)

Curated subset of the official Additel command set, focused on what's useful
for a communication test. The full, unabridged list is in
[`226_227_commands.txt`](226_227_commands.txt) (extracted from Additel's
official *Programming Commands for 226 and 227* PDF).

## Command syntax

- A command has a **mnemonic** and (optionally) a **parameter**, separated by a
  space. Example: `MEASure:CH? PV` — mnemonic `MEASure:CH?`, parameter `PV`.
- Parts of the mnemonic in `[]` are **optional**:
  `MEASure[:SCALar]:AELectricity?` ≡ `MEASure:AELectricity?`.
- `(num1:num2)` in a mnemonic marks a numeric range to be replaced by an actual
  number, e.g. `SENSe:ELECtricity:TCCHannel(1:4)?` → `...TCCHannel1?`.
- Angle brackets `<...>` mark parameters — do **not** type the brackets.

## Terminator

Every command **must** end with one of: `\r\n`, `\r`, `\n`, or `\0`.
This tool sends `\r\n` (configurable in code via `DEFAULT_TERMINATOR`).

## IEEE 488.2 common commands

| Command | Description | Returns |
|---|---|---|
| `*IDN?` | Instrument identification. | Serial number, firmware version, sub-module type, name (order varies by firmware — see note below). |
| `*CLS`  | Clear status/event/error registers. | — |
| `*RST`  | Program reset. | — |

> **`*IDN?` field order depends on firmware.** For firmware 26–27 the order is
> *serial, sub-module type, firmware version, name*; for firmware 28+ it is
> *serial, firmware version, sub-module type, name*. Don't hard-code positions.

## Read the current measured value

Use **`MEASure:CH? PV`** — note the required `PV` parameter (separated by a
space). This returns the present value of the active measure channel and works
regardless of the current screen/mode. `AdditelBLE.measure()` sends exactly this.

```
MEASure:CH? PV\r\n
```

## Why a command returns no reply

`*IDN?` always answers (IEEE 488.2 common command, no parameter, no mode). Most
other commands don't answer unless used correctly:

- **Missing parameter.** Per the manual §1, mnemonic and parameter are separated
  by a space. `MEASure:CH?` alone → no reply; `MEASure:CH? PV` → replies.
- **Wrong mode.** `CALibrator:...` commands only reply in **Calibrator mode**;
  other commands depend on the active function.
- **Set commands** (e.g. `...:UNIT <id>`) legitimately return nothing.

**Diagnose it:** the device queues the reason instead of replying. Read it with
**`SYSTem:ERRor?`** (or `AdditelBLE.error()`) right after the silent command —
it returns the error (bad parameter / wrong mode / unknown header), or
`0,"No error"`. Mode-independent commands that always reply and are good for a
smoke test: `SYSTem:VERSion?`, `SYSTem:DATE?`, `SYSTem:BLUEtooth:NAMe`,
`SYSTem:BATTery:CAPacity?`.

## Measurement (Calibrator mode)

> These require the device to be in **Calibrator mode**.

| Command | Description | Returns |
|---|---|---|
| `CALibrator:MEASure:VALUE?` | Read the measured value of the current channel. | Value(s) + unit ID; shape depends on the active function (V, mA, mV, Hz, external pressure module, pulse, switch, HART, TC, RTD, ...). |
| `CALibrator:MEASure:FUNCtion?` | Read the current measure item. | Measure item (e.g. `EM_V`). |
| `CALibrator:MEASure:FUNCtion <item>` | Set the current measure item. | — |
| `CALibrator:MEASure:RANGe?` | Read the range of the current measure item. | Range info. |

## External pressure module

| Command | Description | Returns |
|---|---|---|
| `CALibrator:MEASure:PRESsure:UNIT?` | Read the pressure unit. | Pressure unit ID. |
| `CALibrator:MEASure:PRESsure:UNIT <id>` | Set the pressure unit. | — |
| `CALibrator:MEASure:PRESsure:PTYPe?` | Read pressure type (G/A/D). | Pressure type. |
| `CALibrator:MEASure:PRESsure:ZERO` | Zero the pressure module. | — |
| `CALibrator:MEASure:PRESsure:STABle?` | Read pressure-module stability. | `0` / `1`. |
| `CALibrator:MEASure:PRESsure:RESolution?` | Read pressure resolution. | Resolution. |

## Handy examples

```
*IDN?\r\n
CALibrator:MEASure:VALUE?\r\n
CALibrator:MEASure:PRESsure:UNIT?\r\n
```

With the CLI:

```bash
adt-ble send "*IDN?" "CALibrator:MEASure:PRESsure:UNIT?"
```

From the library:

```python
async with AdditelBLE(name="ADT226") as dev:
    print(await dev.query("CALibrator:MEASure:PRESsure:UNIT?"))
```

For anything not listed here (signal output, HART, thermal calculation, channel
configuration, status registers, ...), consult
[`226_227_commands.txt`](226_227_commands.txt).
