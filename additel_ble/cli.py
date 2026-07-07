"""Test CLI for the additel_ble library, built with Typer + Rich.

A thin layer over the library, using only its public API. Install with the
``cli`` extra (``pip install "additel-ble[cli]"``).

Two commands, matching the natural flow:

    adt-ble scan                       # 1) find devices (address + name)
    adt-ble send "*IDN?"               # 2) connect, send command(s), disconnect

Connect by name (default) or straight by address/UUID::

    adt-ble send --name ADT226 "*IDN?"
    adt-ble send --uuid 1234ABCD-...   "*IDN?" "CALibrator:MEASure:VALUE?"
"""

from __future__ import annotations

import logging
from typing import List, Optional

try:
    import typer
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.table import Table
except ImportError as exc:  # pragma: no cover - dependency hint
    raise SystemExit(
        "The CLI needs extra dependencies. Install them with:\n"
        '    pip install "additel-ble[cli]"'
    ) from exc

from bleak.exc import BleakError

from . import __version__
from .client import AdditelBLE
from .exceptions import AdditelError, CommandTimeoutError
from .scanner import scan as scan_devices

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Scan and talk to Additel calibrators over Bluetooth Low Energy.",
)
console = Console()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False, markup=True)],
    )


def _run(coro):
    """Run a coroutine, mapping library errors to clean CLI output."""
    import asyncio

    try:
        return asyncio.run(coro)
    except AdditelError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except BleakError as exc:
        console.print(f"[red]Bluetooth error:[/red] {exc}")
        console.print("[yellow]Tip:[/yellow] run with [b]-v[/b] to see the GATT table.")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:  # pragma: no cover
        raise typer.Exit(code=130)


def _print_gatt(rows, notify_uuid, write_uuid) -> None:
    table = Table(title="GATT table")
    table.add_column("Service", style="dim")
    table.add_column("Characteristic", style="cyan")
    table.add_column("Properties", style="magenta")
    for service_uuid, char_uuid, props in rows:
        mark = ""
        if char_uuid.lower() == (notify_uuid or "").lower():
            mark += " [green]◀ notify[/green]"
        if char_uuid.lower() == (write_uuid or "").lower():
            mark += " [yellow]◀ write[/yellow]"
        table.add_row(service_uuid, char_uuid + mark, ", ".join(props))
    console.print(table)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"additel-ble {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Additel-BLE — BLE test toolkit for Additel calibrators."""


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

@app.command()
def scan(
    timeout: float = typer.Option(10.0, "--timeout", "-t", help="Scan duration (seconds)."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Filter by name substring."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs."),
) -> None:
    """Scan and list nearby BLE devices (address + name)."""
    _setup_logging(verbose)
    devices = _run(scan_devices(timeout))
    if name:
        devices = [d for d in devices if d.name and name.lower() in d.name.lower()]

    table = Table(title=f"BLE devices ({len(devices)})")
    table.add_column("Address", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    for dev in devices:
        table.add_row(str(dev.address), dev.name or "[dim]<no name>[/dim]")
    console.print(table)


@app.command()
def send(
    command: Optional[List[str]] = typer.Argument(
        None, help="SCPI command(s) to send. Default: *IDN?"
    ),
    name: str = typer.Option(
        "ADT226", "--name", "-n", help="Connect to the first device whose name contains this."
    ),
    address: Optional[str] = typer.Option(
        None, "--address", "--uuid", "-a",
        help="Connect straight to this address/UUID (skips the name scan).",
    ),
    at_prefix: bool = typer.Option(False, "--at-prefix", help="Prefix commands with '@'."),
    timeout: float = typer.Option(3.0, "--timeout", "-t", help="Per-command reply timeout (s)."),
    scan_timeout: float = typer.Option(10.0, "--scan-timeout", help="Scan duration (s)."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Also print the GATT table (UUIDs) and debug logs."
    ),
) -> None:
    """Connect (by name or address), send command(s), print the replies, disconnect."""
    _setup_logging(verbose)
    commands = list(command) if command else ["*IDN?"]

    async def _impl():
        async with AdditelBLE(
            name=name, address=address, scan_timeout=scan_timeout,
            command_timeout=timeout, at_prefix=at_prefix,
        ) as dev:
            console.print(
                f"[green]Connected[/green] to [bold]{dev.address}[/bold]  "
                f"[dim](notify {dev.notify_uuid} · write {dev.write_uuid})[/dim]\n"
            )
            if verbose:
                _print_gatt(dev.gatt_table(), dev.notify_uuid, dev.write_uuid)
            for cmd in commands:
                try:
                    reply = await dev.query(cmd)
                    console.print(f"  [cyan]{cmd}[/cyan] → [green]{reply}[/green]")
                except CommandTimeoutError:
                    console.print(f"  [cyan]{cmd}[/cyan] → [yellow](sent, no reply)[/yellow]")
                except BleakError as exc:
                    console.print(f"  [cyan]{cmd}[/cyan] → [red]GATT error: {exc}[/red]")
        console.print("\n[dim]Disconnected.[/dim]")

    _run(_impl())


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
