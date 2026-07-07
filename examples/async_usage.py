"""Async integration example.

Run:  python examples/async_usage.py
"""

import asyncio

from additel_ble import AdditelBLE, AdditelError


async def main() -> None:
    # `async with` connects, does the CODE? handshake and disconnects for you.
    try:
        async with AdditelBLE(name="ADT226") as dev:
            print("Connected to:", dev.address)
            print("Notify/Write UUID:", dev.notify_uuid, "/", dev.write_uuid)

            print("IDN     :", await dev.identify())
            print("Measure :", await dev.measure())

            # Any SCPI command works:
            print("Unit    :", await dev.query("CALibrator:MEASure:PRESsure:UNIT?"))
    except AdditelError as exc:
        print("BLE error:", exc)


if __name__ == "__main__":
    asyncio.run(main())
