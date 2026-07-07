<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="ADT BLE" width="300">
  </picture>
</p>

<p align="center">
  <b>Libreria Python integrabile per la comunicazione Bluetooth Low Energy con i calibratori Additel</b><br>
  <sub>+ una CLI di test separata &nbsp;·&nbsp; target primario <b>ADT226</b> (compatibile ADT227 e varianti <code>…Ex</code>)</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-64748b" alt="Platforms">
  <img src="https://img.shields.io/badge/BLE-Bleak-4f46e5?logo=bluetooth&logoColor=white" alt="Bleak">
  <img src="https://img.shields.io/badge/CLI-Typer-009485" alt="Typer">
  <img src="https://img.shields.io/badge/license-MIT-16a34a" alt="MIT">
</p>

---

**ADT-BLE** è composto da due parti:

1. **`additel_ble`** — una **libreria** pulita e integrabile in altri programmi, con dipendenza core solo su [`bleak`](https://bleak.readthedocs.io). Offre un'API **async** (`AdditelBLE`) e una **sincrona** (`AdditelBLESync`) per l'uso anche in programmi non-async.
2. **`adt-ble`** — una **CLI di test** separata (basata su [Typer](https://typer.tiangolo.com) + [Rich](https://rich.readthedocs.io)), installabile come extra opzionale.

La libreria gestisce: scan/connessione, risoluzione delle characteristic GATT (**override → UUID documentati → auto-discovery**), handshake `CODE?`, buffering delle risposte BLE frammentate e un'API comandi `query`/`write` con gestione degli errori tipizzata.

> ⚙️ **Cross-platform**: macOS, Windows e Linux senza modifiche (Bleak usa CoreBluetooth / WinRT / BlueZ).

## Indice

- [Funzionalità](#funzionalità)
- [Installazione](#installazione)
- [Uso come libreria](#uso-come-libreria)
- [API reference](#api-reference)
- [CLI di test (`adt-ble`)](#cli-di-test-adt-ble)
- [Come ottenere/recuperare gli UUID](#come-ottenerrecuperare-gli-uuid) 🔑
- [Come funziona](#come-funziona)
- [Note per piattaforma](#note-per-piattaforma)
- [Struttura del progetto](#struttura-del-progetto)
- [Sviluppo & test](#sviluppo--test)
- [Riferimenti](#riferimenti)
- [Licenza](#licenza)

## Funzionalità

- 📦 **Libreria integrabile** — dipendenza core solo `bleak`, tipizzata (`py.typed`).
- 🔀 **API async e sync** — usala con `async/await` o come API bloccante.
- 🧩 **Auto-discovery degli UUID** (con override manuale).
- 📥 **Buffering** delle risposte BLE frammentate + handshake `CODE?`.
- 🧱 **Errori tipizzati** (`AdditelError` e sottoclassi).
- 🖥️ **CLI di test** con Typer/Rich (scan, gatt, test, query).
- ✅ **Testata** (pytest) e **cross-platform**.

## Installazione

**Come libreria** (integrazione in un altro programma):

```bash
# da sorgente locale
pip install .

# oppure direttamente da GitHub
pip install "git+https://github.com/riccardo-nigrelli/ADT-BLE.git"
```

**Con la CLI di test** (extra `cli`):

```bash
pip install ".[cli]"
# o da GitHub:
pip install "additel-ble[cli] @ git+https://github.com/riccardo-nigrelli/ADT-BLE.git"
```

**Ambiente di sviluppo** (editable + CLI + test):

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt   # -e .[cli,dev]
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

## Uso come libreria

### Async (consigliato)

```python
import asyncio
from additel_ble import AdditelBLE

async def main():
    async with AdditelBLE(name="ADT226") as dev:      # connette + handshake
        print("IDN:", await dev.identify())            # *IDN?
        print("Val:", await dev.measure())             # CALibrator:MEASure:VALUE?
        print("Unit:", await dev.query("CALibrator:MEASure:PRESsure:UNIT?"))

asyncio.run(main())
```

### Sincrono (programmi non-async)

```python
from additel_ble import AdditelBLESync

with AdditelBLESync(name="ADT226") as dev:
    print("IDN:", dev.identify())
    print("Val:", dev.query("CALibrator:MEASure:VALUE?"))
```

### Gestione errori

```python
from additel_ble import AdditelBLE, DeviceNotFoundError, CommandTimeoutError, AdditelError

async with AdditelBLE(name="ADT226", scan_timeout=15) as dev:
    try:
        print(await dev.query("*IDN?", timeout=2))
    except CommandTimeoutError:
        print("nessuna risposta")
# tutte le eccezioni della libreria derivano da AdditelError
```

Esempi completi in [`examples/`](examples/).

## API reference

### `AdditelBLE(name="ADT226", address=None, *, notify_uuid=None, write_uuid=None, at_prefix=False, terminator="\r\n", scan_timeout=10.0, command_timeout=3.0, ready_timeout=5.0)`

Client BLE asincrono.

| Metodo / proprietà | Descrizione |
|---|---|
| `await connect()` → self | Scan (se serve), connessione, risoluzione characteristic, handshake. |
| `await disconnect()` | Chiude notifiche e connessione (idempotente). |
| `async with ...` | `connect()`/`disconnect()` automatici. |
| `await query(cmd, *, timeout=None)` → `str` | Invia un comando e ritorna la risposta (solleva `CommandTimeoutError`). |
| `await write(cmd)` | Invia senza attendere risposta. |
| `await identify()` → `str` | Scorciatoia per `*IDN?`. |
| `await measure()` → `str` | Scorciatoia per `CALibrator:MEASure:VALUE?`. |
| `gatt_table()` → `list[(service, char, props)]` | Tabella GATT (per scoprire gli UUID). |
| `is_connected`, `ready`, `address`, `notify_uuid`, `write_uuid` | Proprietà di stato. |

> **Comandi con/senza risposta:** usa **`query()`** per i comandi che rispondono —
> tutti quelli con `?` e i "set" che ritornano `0|1` — attende e ritorna la risposta.
> Usa **`write()`** per i "set" che non rispondono (invio senza attesa). La scrittura
> usa automaticamente *write-without-response* quando la characteristic la supporta.

### `AdditelBLESync(...)`
Stessa firma e stessi metodi, ma **bloccanti** (usa un event loop in un thread dedicato). Supporta `with`.

### Funzioni & eccezioni
- `await scan(timeout=10.0)` / `scan_sync(timeout=10.0)` — elenco device BLE.
- `await find_device(name, *, timeout=10.0)` — primo device che matcha (solleva `DeviceNotFoundError`).
- `ResponseBuffer`, `build_command(...)` — primitive di protocollo riusabili.
- Eccezioni: `AdditelError` (base), `DeviceNotFoundError`, `ConnectionFailedError`, `CharacteristicNotFoundError`, `CommandTimeoutError`.

## CLI di test (`adt-ble`)

Due comandi, semplici e chiari: **`scan`** e **`send`**.

```bash
adt-ble --help
adt-ble scan                          # 1) elenca i device BLE vicini (indirizzo + nome)
adt-ble scan --name ADT               #    filtra per nome
adt-ble uuid ADT226                   #    mostra l'indirizzo/UUID del device dato il nome

adt-ble send "*IDN?"                   # 2) connetti (nome ADT226 di default), invia, disconnetti
adt-ble send --name ADT227 "*IDN?"     #    connetti per NOME
adt-ble send --uuid <ADDRESS> "*IDN?"  #    oppure per INDIRIZZO/UUID
adt-ble send "*IDN?" "CALibrator:MEASure:PRESsure:UNIT?"   # più comandi in sequenza
adt-ble send -v "*IDN?"                #    -v mostra anche la tabella GATT (UUID)
adt-ble send --at-prefix "*IDN?"       #    alcuni firmware vogliono il prefisso '@'
```

`adt-ble send` senza comando invia `*IDN?`. In alternativa: `python -m additel_ble.cli ...`.

## Come ottenere/recuperare gli UUID

La comunicazione usa due characteristic GATT: una con **`notify`/`indicate`** (risposte) e una con **`write`/`write-without-response`** (comandi), spesso la stessa.

> ℹ️ **Di norma non serve fare nulla:** la libreria prova gli UUID documentati e, se assenti sul tuo modello, li **scopre da sola**. Ti servono espliciti solo per *verificarli*, *fissarli*, o se l'auto-discovery sbaglia.

**Dalla CLI** — il modo più semplice:

```bash
adt-ble scan          # 1) trova nome/indirizzo del device
adt-ble send -v       # 2) connette e stampa la tabella GATT (con -v)
```

`adt-ble send -v` mostra la tabella GATT ed evidenzia le characteristic scelte
per notify/write (visibili anche nella riga "Connected to …").

Per **fissare** gli UUID in un tuo programma, passali al costruttore della libreria:

```python
AdditelBLE(
    name="ADT226",
    notify_uuid="1B6B9415-FF0D-47C2-9444-A5032F727B2D",
    write_uuid="1B6B9415-FF0D-47C2-9444-A5032F727B2D",
)
```

**Dalla libreria**:

```python
async with AdditelBLE(name="ADT226") as dev:
    for service, char, props in dev.gatt_table():
        print(service, char, props)
    print("notify:", dev.notify_uuid, " write:", dev.write_uuid)
```

**Metodo alternativo — app BLE esterna**: nRF Connect (Android/iOS), *Bluetooth LE Explorer* (Windows Store), *LightBlue* / *Bluetooth Explorer* (macOS), `bluetoothctl` (Linux).

> **UUID documentati da Additel** (validi per l'ADT685, punto di partenza — *possono differire*):
> service `AF661820-D14A-4B21-90F8-54D58F8614F0`, notify/write `1B6B9415-FF0D-47C2-9444-A5032F727B2D`.

## Come funziona

- **Trasporto UART-over-GATT**: si scrive su una *write characteristic*, le risposte arrivano via **notifiche**.
- Dopo l'iscrizione il device invia una volta **`CODE?`** = pronto (non serve rispondere).
- Comandi = stringhe **SCPI** terminate da `\r\n`; risposte spesso **frammentate** → bufferizzate fino al terminatore.
- Risoluzione characteristic: **override → UUID documentati → auto-discovery** dalle proprietà.

Dettagli in [`docs/additel_ble_notes.md`](docs/additel_ble_notes.md); comandi in [`docs/scpi_commands.md`](docs/scpi_commands.md).

## Note per piattaforma

| Sistema | Note |
|---|---|
| **macOS** | Primo avvio: concedi il permesso **Bluetooth** all'app/terminale (*Impostazioni → Privacy e sicurezza → Bluetooth*). Gli indirizzi sono **UUID** di sistema. |
| **Windows** | **Windows 10 (16299+) / 11**, Bluetooth attivo. Indirizzi **MAC**. |
| **Linux** | **BlueZ ≥ 5.43**, servizio `bluetooth` attivo. Indirizzi **MAC**. |

## Struttura del progetto

```
ADT-BLE/
├── additel_ble/              # la libreria (import: additel_ble)
│   ├── __init__.py           # API pubblica
│   ├── client.py             # AdditelBLE (core async)
│   ├── sync.py               # AdditelBLESync (facciata sync)
│   ├── scanner.py            # scan / find_device
│   ├── protocol.py           # costanti + ResponseBuffer (senza dip. BLE)
│   ├── exceptions.py         # gerarchia eccezioni
│   ├── cli.py                # CLI Typer di test (adt-ble)
│   └── py.typed
├── examples/                 # async_usage.py, sync_usage.py
├── tests/                    # test_protocol.py (pytest)
├── docs/                     # note BLE, reference SCPI, materiale ufficiale Additel
├── assets/                   # logo light/dark
├── pyproject.toml
├── requirements.txt
├── README.md
└── LICENSE
```

## Sviluppo & test

```bash
python -m pip install -r requirements.txt   # editable + cli + dev
pytest                                       # esegue i test (protocol/buffering)
adt-ble scan                                 # prova reale dell'adapter BLE
```

## Riferimenti

- Repo ufficiale Additel — *Additel Device Communication*: <https://github.com/Additel-Code/Additel-Device-Communication>
- Guida BLE ufficiale: <https://github.com/Additel-Code/Additel-Device-Communication/blob/main/Bluetooth/bluetooth.md>
- Programming Commands 226/227 (PDF): <https://additel.com/download/programming_commands/226%20227/Programming%20Commands%20for%20226%20and%20227.pdf>
- Manuale utente 226/227 (PDF): <https://additel.com/download/user%20manual/226%20227%20User%20Manual.pdf>
- Bleak: <https://bleak.readthedocs.io> · Typer: <https://typer.tiangolo.com> · Rich: <https://rich.readthedocs.io>

## Licenza

Distribuito con licenza [MIT](LICENSE).
