"""Test CLI for the additel_ble library, built with Typer + Rich.

This is a thin, separate layer on top of the library: it only uses the public
API. Install it with the ``cli`` extra::

    pip install "additel-ble[cli]"

Then::

    adt-ble scan
    adt-ble gatt            # discover the device UUIDs
    adt-ble test
    adt-ble query "*IDN?"
"""

from __future__ import annotations

import asyncio
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

from . import __version__
from .client import AdditelBLE
from .exceptions import AdditelError, CommandTimeoutError
from .scanner import scan as scan_devices

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Test BLE communication with Additel calibrators (ADT226 by default).",
)
console = Console()

DEFAULT_COMMANDS = ["*IDN?", "CALibrator:MEASure:VALUE?"]


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
    try:
        return asyncio.run(coro)
    except AdditelError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:  # pragma: no cover
        raise typer.Exit(code=130)


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
    timeout: float = typer.Option(10.0, help="Scan duration (seconds)."),
    name: Optional[str] = typer.Option(None, help="Filter by name substring."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """List nearby BLE devices."""
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
def gatt(
    name: str = typer.Option("ADT226", help="Advertised name to scan for."),
    address: Optional[str] = typer.Option(None, help="Connect directly to this address."),
    scan_timeout: float = typer.Option(10.0, help="Scan duration (seconds)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Connect and print the GATT table — use this to discover the UUIDs."""
    _setup_logging(verbose)

    async def _impl():
        dev = AdditelBLE(name=name, address=address, scan_timeout=scan_timeout)
        await dev.connect()
        try:
            return dev.gatt_table(), dev.notify_uuid, dev.write_uuid, dev.address
        finally:
            await dev.disconnect()

    rows, notify_uuid, write_uuid, addr = _run(_impl())

    console.print(f"Connected to [bold]{addr}[/bold]\n")
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
    console.print(
        f"\nSelected → [green]--notify-uuid[/green] {notify_uuid}  "
        f"[yellow]--write-uuid[/yellow] {write_uuid}"
    )


@app.command()
def test(
    name: str = typer.Option("ADT226", help="Advertised name to scan for."),
    address: Optional[str] = typer.Option(None, help="Connect directly to this address."),
    scan_timeout: float = typer.Option(10.0, help="Scan duration (seconds)."),
    timeout: float = typer.Option(3.0, help="Per-command reply timeout (seconds)."),
    notify_uuid: Optional[str] = typer.Option(None, help="Override notify characteristic UUID."),
    write_uuid: Optional[str] = typer.Option(None, help="Override write characteristic UUID."),
    at_prefix: bool = typer.Option(False, "--at-prefix", help="Prefix commands with '@'."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Connect and run the default communication check (*IDN? + a measurement)."""
    _setup_logging(verbose)

    async def _impl():
        results = []
        async with AdditelBLE(
            name=name, address=address, scan_timeout=scan_timeout,
            command_timeout=timeout, notify_uuid=notify_uuid,
            write_uuid=write_uuid, at_prefix=at_prefix,
        ) as dev:
            console.print(
                f"Connected to [bold]{dev.address}[/bold] "
                f"({'ready' if dev.ready else 'no CODE? signal'})\n"
            )
            for command in DEFAULT_COMMANDS:
                try:
                    results.append((command, await dev.query(command)))
                except CommandTimeoutError:
                    results.append((command, None))
        return results

    results = _run(_impl())
    table = Table(title="Communication test")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Reply", style="green")
    for command, reply in results:
        table.add_row(command, reply if reply is not None else "[red](no reply)[/red]")
    console.print(table)


@app.command()
def query(
    commands: List[str] = typer.Argument(..., help="One or more SCPI commands."),
    name: str = typer.Option("ADT226", help="Advertised name to scan for."),
    address: Optional[str] = typer.Option(None, help="Connect directly to this address."),
    scan_timeout: float = typer.Option(10.0, help="Scan duration (seconds)."),
    timeout: float = typer.Option(3.0, help="Per-command reply timeout (seconds)."),
    at_prefix: bool = typer.Option(False, "--at-prefix", help="Prefix commands with '@'."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Send one or more SCPI commands and print the replies."""
    _setup_logging(verbose)

    async def _impl():
        results = []
        async with AdditelBLE(
            name=name, address=address, scan_timeout=scan_timeout,
            command_timeout=timeout, at_prefix=at_prefix,
        ) as dev:
            console.print(f"Connected to [bold]{dev.address}[/bold]\n")
            for command in commands:
                try:
                    results.append((command, await dev.query(command)))
                except CommandTimeoutError:
                    results.append((command, None))
        return results

    results = _run(_impl())
    for command, reply in results:
        if reply is None:
            console.print(f"[cyan]{command}[/cyan] → [red](no reply)[/red]")
        else:
            console.print(f"[cyan]{command}[/cyan] → [green]{reply}[/green]")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
