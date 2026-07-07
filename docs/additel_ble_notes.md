# Note tecniche — comunicazione BLE con dispositivi Additel

Sintesi di come funziona la comunicazione Bluetooth Low Energy con i
calibratori Additel (serie 226/227 e affini), ricavata dal materiale
ufficiale Additel. Vedi i file allegati in questa cartella e i link nel
[`../README.md`](../README.md).

## Modello di comunicazione

I dispositivi Additel recenti espongono una **UART-over-GATT**: si scrive un
comando testuale su una characteristic e si ricevono le risposte via
**notifiche** su un'altra characteristic (spesso la *stessa*).

Passi (dall'esempio ufficiale in Python + [Bleak](https://bleak.readthedocs.io),
libreria **cross-platform**: macOS / Windows / Linux):

1. **Scan** dei dispositivi BLE vicini.
2. **Filtro per nome** advertised (es. `ADT685`; per il nostro modello `ADT226`).
3. **Connessione** con `BleakClient`.
4. **Subscribe** alla *notification characteristic* per ricevere le risposte
   (arrivano come `bytearray`).
5. **Handshake**: il dispositivo invia spontaneamente **`CODE?`**; il client
   **deve rispondere `@\r\n` entro ~5 secondi**, altrimenti il device chiude la
   connessione e **ignora tutti i comandi**. Solo dopo l'handshake risponde.
   (Documentato nel *Bluetooth Protocol for the ADT685*, che usa gli stessi
   UUID del 226/227.)
6. **Scrittura** del comando sulla *write characteristic*, come `bytes` UTF-8.
7. Le risposte arrivano nella callback delle notifiche.

> ⚠️ La guida BLE generica del 226 diceva che dopo `CODE?` "si può iniziare a
> inviare comandi" **senza rispondere** — è **errato/incompleto**: senza
> l'handshake `@` il device 226 non risponde e si disconnette dopo ~5s.

## UUID

> ⚠️ Additel dichiara che questi UUID sono per l'**ADT685** e **possono
> differire** su altri modelli. Per questo lo script prova prima questi e,
> se non presenti, fa **auto-discovery** dalle proprietà delle characteristic
> (`notify`/`indicate` per leggere, `write`/`write-without-response` per scrivere).

| Ruolo | UUID (ADT685, valore di partenza) |
|-------|-----------------------------------|
| Communication service | `AF661820-D14A-4B21-90F8-54D58F8614F0` |
| Notification characteristic | `1B6B9415-FF0D-47C2-9444-A5032F727B2D` |
| Write characteristic | `1B6B9415-FF0D-47C2-9444-A5032F727B2D` |

**Per scoprire gli UUID reali del tuo dispositivo** usa `adt-ble send -v` (CLI)
oppure `AdditelBLE.gatt_table()` dalla libreria: ottieni l'intera tabella GATT
(service + characteristic con le proprietà) e le characteristic scelte per
notify/write. Vedi
la sezione *"Come ottenere/recuperare gli UUID"* del README per la procedura
completa e le alternative (nRF Connect, `bluetoothctl`, ecc.).

## Formato dei comandi (SCPI)

- I comandi sono stringhe SCPI (vedi [`scpi_commands.md`](scpi_commands.md) e
  [`226_227_commands.txt`](226_227_commands.txt)).
- **Terminatore**: uno tra `\r\n`, `\r`, `\n`, `\0`. Lo script usa `\r\n`.
- Struttura: *mnemonico* + spazio + *parametro* (es. `MEASure:CH? PV`).
- Le parti in `[]` del mnemonico sono opzionali.
- Il `@` **non** è un prefisso da anteporre a ogni comando: è il **token di
  handshake** una tantum in risposta a `CODE?` (vedi punto 5). La libreria lo
  invia in automatico (`AdditelBLE(handshake="@")`, default).
- Le risposte BLE possono arrivare **frammentate** su più notifiche: vanno
  bufferizzate fino al terminatore (lo script lo fa).

## Comandi utili per una demo

| Comando | Descrizione |
|---------|-------------|
| `*IDN?` | Identificazione: seriale, versione firmware, modello. Funziona sempre. |
| `*CLS` / `*RST` | Clear registri / reset. |
| `CALibrator:MEASure:VALUE?` | Legge il valore misurato del canale (richiede modalità Calibrator). |
| `CALibrator:MEASure:FUNCtion?` | Legge la voce di misura corrente. |
| `CALibrator:MEASure:PRESsure:UNIT?` | Legge l'unità del modulo di pressione esterno. |
| `CALibrator:MEASure:PRESsure:ZERO` | Azzeramento del modulo di pressione. |
| `CALibrator:MEASure:PRESsure:STABle?` | Stato di stabilità del modulo di pressione. |
| `MEASure:CH? PV` | Acquisisce il valore misurato corrente. |

L'elenco completo (misura, output, HART, calcolo termico, ecc.) è in
[`226_227_commands.txt`](226_227_commands.txt).

## File di riferimento in questa cartella

- [`scpi_commands.md`](scpi_commands.md) — reference SCPI curata.
- [`226_227_commands.txt`](226_227_commands.txt) — command set SCPI 226/227 completo (estratto dal PDF ufficiale).
- [`additel_official_bluetooth_guide.md`](additel_official_bluetooth_guide.md) — guida BLE ufficiale Additel (copia).
- [`additel_official_bluetooth_example.py`](additel_official_bluetooth_example.py) — esempio Python ufficiale (copia).
