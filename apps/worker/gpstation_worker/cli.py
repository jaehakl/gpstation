from __future__ import annotations

import asyncio
import json

import typer

from gpstation_worker import __version__
from gpstation_worker.config import load_settings
from gpstation_worker.gpu import get_gpu_status
from gpstation_worker.ws_client import run_worker

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@app.command()
def run() -> None:
    settings = load_settings()
    try:
        asyncio.run(run_worker(settings))
    except KeyboardInterrupt:
        typer.echo("Stopped.")
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("config-check")
def config_check() -> None:
    settings = load_settings()
    safe_settings = {
        "api_url": settings.api_url,
        "websocket_url": settings.websocket_url,
        "worker_name": settings.worker_name,
        "gpu_interval_sec": settings.gpu_interval_sec,
        "access_key": "set" if settings.access_key else "missing",
    }
    typer.echo(json.dumps(safe_settings, ensure_ascii=False, indent=2))


@app.command("gpu-info")
def gpu_info() -> None:
    typer.echo(json.dumps(get_gpu_status().to_dict(), ensure_ascii=False, indent=2))


@app.command()
def version() -> None:
    typer.echo(__version__)
