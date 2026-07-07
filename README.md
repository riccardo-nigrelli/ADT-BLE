<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="Additel·BT" width="460">
  </picture>
</p>

<p align="center">
  <b>Toolkit da riga di comando per comunicare via Bluetooth Low Energy con i calibratori Additel</b><br>
  <sub>Target primario: <b>ADT226</b> — compatibile con ADT227 e varianti <code>…Ex</code></sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-64748b" alt="Platforms">
  <img src="https://img.shields.io/badge/BLE-Bleak-4f46e5?logo=bluetooth&logoColor=white" alt="Bleak">
  <img src="https://img.shields.io/badge/license-MIT-16a34a" alt="MIT">
</p>

---

**Additel·BT** scansiona, si connette e dialoga via BLE con un calibratore
Additel: trova il device → si connette → si iscrive alle notifiche → attende il
segnale di pronto `CODE?` → invia comandi **SCPI** (es. `*IDN?`, lettura misura)
→ stampa le risposte → si disconnette.

È basato sull'esempio ufficiale Additel (Python + libreria
[Bleak](https://bleak.readthedocs.io)), con in più: **auto-discovery degli
UUID**, buffering delle risposte frammentate, attesa esplicita di ogni
risposta (niente `sleep` fissi), override degli UUID e gestione degli errori.

> ⚙️ **Cross-platform**: gira su **macOS, Windows e Linux** senza modifiche —
> Bleak usa CoreBluetooth / WinRT / BlueZ a seconda del sistema.

## Indice

- [Funzionalità](#funzionalità)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Uso](#uso)
- [Come ottenere/recuperare gli UUID](#come-ottenerrecuperare-gli-uuid) 🔑
- [Come funziona](#come-funziona)
- [Note per piattaforma & permessi](#note-per-piattaforma--permessi)
- [Troubleshooting](#troubleshooting)
- [Struttura del progetto](#struttura-del-progetto)
- [Riferimenti](#riferimenti)
- [Licenza](#licenza)

## Funzionalità

- 🔍 **Scan & match** del device per nome advertised (o connessione diretta per indirizzo).
- 🔗 **Connessione BLE** e risoluzione automatica delle characteristic di I/O.
- 🧩 **Auto-discovery degli UUID** (con possibilità di override manuale).
- 📥 **Buffering** delle risposte BLE frammentate fino al terminatore.
- ⏱️ **Attesa per-comando** con timeout (nessun `sleep` a caso).
- 🖥️ **Cross-platform** e **zero dipendenze** oltre a `bleak`.

## Requisiti

- **Python 3.8+**
- **Bluetooth** attivo sul computer (adattatore BLE)
- Il **calibratore Additel** acceso, con Bluetooth abilitato, nel raggio d'azione (fino a ~20 m in campo libero)

## Installazione

```bash
git clone git@github.com:riccardo-nigrelli/Additel-BT.git
cd Additel-BT
```

Crea un ambiente virtuale e installa le dipendenze:

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
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

## Uso

```bash
# Scan del device "ADT226" e verifica comunicazione (default)
python additel_bt.py

# Elenca solo i dispositivi BLE vicini (utile per trovare nome/indirizzo)
python additel_bt.py --scan-only

# Modalità verbosa: stampa tutti i device + la tabella GATT (UUID) + RX/TX grezzi
python additel_bt.py -v

# Nome diverso (es. ADT227) o match parziale
python additel_bt.py --name ADT227

# Connessione diretta a un indirizzo (MAC su Windows/Linux, UUID su macOS)
python additel_bt.py --address AA:BB:CC:DD:EE:FF

# Comandi SCPI personalizzati
python additel_bt.py --commands "*IDN?" "CALibrator:MEASure:PRESsure:UNIT?"

# UUID espliciti (vedi la sezione dedicata più sotto)
python additel_bt.py --notify-uuid <UUID> --write-uuid <UUID>

# Alcuni firmware richiedono il prefisso '@' sui comandi
python additel_bt.py --at-prefix
```

### Output atteso (esempio)

```
10:12:01 INFO    Scanning for BLE devices for 10s...
10:12:11 INFO    Found device: ADT226 (AA:BB:CC:DD:EE:FF)
10:12:11 INFO    Connecting...
10:12:12 INFO    Connected.
10:12:12 INFO    Notify characteristic: 1B6B9415-FF0D-47C2-9444-A5032F727B2D
10:12:12 INFO    Write  characteristic: 1B6B9415-FF0D-47C2-9444-A5032F727B2D (with-response)
10:12:12 INFO    Device ready (received 'CODE?').
10:12:12 INFO    *IDN?                            -> ADDITEL,ADT226,<serial>,<fw>
10:12:13 INFO    CALibrator:MEASure:VALUE?        -> <valore misurato>
10:12:13 INFO    Disconnected. Done.
```

### Opzioni CLI

| Opzione | Default | Descrizione |
|---|---|---|
| `--name` | `ADT226` | Nome advertised da cercare (substring, case-insensitive). |
| `--address` | — | Connessione diretta a un indirizzo BLE (salta lo scan per nome). |
| `--scan-only` | off | Solo scan: elenca i device BLE vicini ed esce. |
| `--scan-timeout` | `10` | Durata dello scan (s). |
| `--timeout` | `3` | Timeout per la risposta a ciascun comando (s). |
| `--ready-timeout` | `5` | Attesa del segnale `CODE?` (s). |
| `--commands` | `*IDN?` `CALibrator:MEASure:VALUE?` | Comandi SCPI da inviare. |
| `--notify-uuid` | auto | Forza l'UUID della *notification characteristic*. |
| `--write-uuid` | auto | Forza l'UUID della *write characteristic*. |
| `--at-prefix` | off | Antepone `@` a ogni comando. |
| `-v`, `--verbose` | off | Dump tabella GATT (UUID) + RX/TX grezzi. |

Codici di uscita: `0` ok · `2` device non trovato · `3` connessione fallita ·
`4` errore Bluetooth · `130` interrotto.

## Come ottenere/recuperare gli UUID

La comunicazione BLE avviene su due *characteristic* GATT: una con proprietà
**`notify`/`indicate`** (da cui arrivano le risposte) e una con
**`write`/`write-without-response`** (su cui si inviano i comandi). Spesso è la
**stessa** characteristic.

> ℹ️ **Nella maggior parte dei casi non devi fare nulla:** lo script prova prima
> gli UUID documentati da Additel e, se non presenti sul tuo modello, li
> **scopre da solo** in base alle proprietà delle characteristic. Ti servono gli
> UUID espliciti solo se vuoi *verificarli*, *fissarli* o se l'auto-discovery
> sceglie la characteristic sbagliata (device con più characteristic scrivibili).

### Metodo consigliato — dallo script (`-v`)

1. **Trova il device** e verifica il nome:
   ```bash
   python additel_bt.py --scan-only
   ```
2. **Connettiti in modalità verbosa** per stampare l'intera tabella GATT:
   ```bash
   python additel_bt.py -v          # oppure: --address <indirizzo> -v
   ```
3. Nell'output cerca il blocco **`GATT table`**. Ogni riga `char` mostra
   **UUID** e **proprietà**:
   ```
   GATT table (services / characteristics / properties):
     service  af661820-d14a-4b21-90f8-54d58f8614f0  (...)
       char   1b6b9415-ff0d-47c2-9444-a5032f727b2d  [write-without-response, notify]  (...)
   ```
   - la characteristic con **`notify`** (o `indicate`) → è la tua `--notify-uuid`;
   - la characteristic con **`write`** (o `write-without-response`) → è la tua `--write-uuid`;
   - se una sola characteristic ha *entrambe* le proprietà, usa quello stesso UUID per tutti e due.
4. Lo script stampa comunque quali ha scelto:
   ```
   Notify characteristic: 1B6B9415-...
   Write  characteristic: 1B6B9415-...
   ```
5. **Fissa gli UUID** (opzionale) per non dipendere dall'auto-discovery:
   ```bash
   python additel_bt.py --notify-uuid 1B6B9415-FF0D-47C2-9444-A5032F727B2D \
                        --write-uuid  1B6B9415-FF0D-47C2-9444-A5032F727B2D
   ```

### Metodo alternativo — app BLE esterna

Puoi ispezionare i servizi/characteristic anche con un explorer BLE generico,
utile per confronto:

- **nRF Connect for Mobile** (Android/iOS, gratis) — connetti il device e apri i
  servizi per vedere UUID e proprietà.
- **Windows**: app *Bluetooth LE Explorer* (Microsoft Store).
- **macOS**: *Bluetooth Explorer* (Additional Tools for Xcode) o app come *LightBlue*.
- **Linux**: `bluetoothctl` → `menu gatt` → `list-attributes`.

> **UUID documentati da Additel** (validi per l'ADT685, punto di partenza —
> *possono differire* su altri modelli):
> - Communication service: `AF661820-D14A-4B21-90F8-54D58F8614F0`
> - Notify/Write characteristic: `1B6B9415-FF0D-47C2-9444-A5032F727B2D`

## Come funziona

- **Trasporto UART-over-GATT**: si scrive su una *write characteristic* e si
  leggono le risposte via **notifiche**.
- Dopo l'iscrizione, il device invia una volta **`CODE?`** = è **pronto** (non
  serve rispondere).
- I comandi sono stringhe **SCPI** terminate da `\r\n`. Le risposte possono
  arrivare **frammentate**: lo script le bufferizza fino al terminatore.
- Risoluzione characteristic: **override CLI → UUID documentati → auto-discovery**.

Dettagli completi in [`docs/additel_ble_notes.md`](docs/additel_ble_notes.md) e
comandi SCPI in [`docs/scpi_commands.md`](docs/scpi_commands.md).

## Note per piattaforma & permessi

| Sistema | Note |
|---|---|
| **macOS** | Al primo avvio serve concedere il permesso **Bluetooth** all'app che lancia lo script (Terminale/IDE). Se lo scan non trova nulla: *Impostazioni di Sistema → Privacy e sicurezza → Bluetooth*. Gli indirizzi sono **UUID** assegnati dal sistema, non MAC. |
| **Windows** | Richiede **Windows 10 (build 16299+) o 11**. Bluetooth attivo. Gli indirizzi sono **MAC** (`AA:BB:CC:DD:EE:FF`). |
| **Linux** | Richiede **BlueZ ≥ 5.43** e il servizio `bluetooth` attivo. Gli indirizzi sono **MAC**. |

## Troubleshooting

| Sintomo | Possibile causa / rimedio |
|---|---|
| "No device matching 'ADT226' found" | Device spento/lontano; Bluetooth off; (macOS) permesso Bluetooth non concesso. Prova `--scan-only`, o `--name ADT` per un match più largo. |
| Connesso ma nessuna risposta | Prova `--at-prefix`; verifica con `-v` le characteristic notify/write; per `CALibrator:MEASure:VALUE?` il device deve essere in **modalità Calibrator**. |
| Auto-discovery sbaglia characteristic | Recupera gli UUID corretti con `-v` e passali con `--notify-uuid`/`--write-uuid`. |
| Nessun `CODE?` | Alcuni firmware potrebbero non inviarlo: lo script prosegue dopo il timeout. |
| `bleak` non si installa | Aggiorna pip (`python -m pip install -U pip`) e verifica Python 3.8+. |

## Struttura del progetto

```
Additel-BT/
├── additel_bt.py                 # tool CLI principale
├── requirements.txt              # dipendenza: bleak
├── README.md
├── LICENSE
├── assets/
│   ├── logo-light.svg
│   └── logo-dark.svg
└── docs/
    ├── additel_ble_notes.md      # come funziona il BLE Additel (tecnico)
    ├── scpi_commands.md          # reference comandi SCPI (curata)
    ├── 226_227_commands.txt      # command set SCPI 226/227 completo (ufficiale)
    ├── additel_official_bluetooth_guide.md    # copia guida ufficiale Additel
    └── additel_official_bluetooth_example.py  # copia esempio ufficiale Additel
```

## Riferimenti

- Repo ufficiale Additel — *Additel Device Communication*:
  <https://github.com/Additel-Code/Additel-Device-Communication>
- Guida BLE ufficiale:
  <https://github.com/Additel-Code/Additel-Device-Communication/blob/main/Bluetooth/bluetooth.md>
- Programming Commands 226/227 (PDF):
  <https://additel.com/download/programming_commands/226%20227/Programming%20Commands%20for%20226%20and%20227.pdf>
- Manuale utente 226/227 (PDF):
  <https://additel.com/download/user%20manual/226%20227%20User%20Manual.pdf>
- Risorse prodotto Additel: <https://additel.com/productresources/>
- Libreria Bleak: <https://bleak.readthedocs.io>

## Licenza

Distribuito con licenza [MIT](LICENSE).
