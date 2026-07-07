"""Synchronous integration example (no async/await needed in your program).

Run:  python examples/sync_usage.py
"""

from additel_ble import AdditelBLESync, AdditelError


def main() -> None:
    try:
        # `with` connects and disconnects for you.
        with AdditelBLESync(name="ADT226") as dev:
            print("Connected to:", dev.address)
            print("IDN     :", dev.identify())
            print("Measure :", dev.measure())
            print("Unit    :", dev.query("CALibrator:MEASure:PRESsure:UNIT?"))
    except AdditelError as exc:
        print("BLE error:", exc)


if __name__ == "__main__":
    main()
