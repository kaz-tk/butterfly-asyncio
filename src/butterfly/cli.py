"""Butterfly CLI entry point."""

import logging
import sys
from pathlib import Path

import click
import uvicorn

from butterfly.config import settings

logger = logging.getLogger("butterfly")


@click.command()
@click.option("--host", default=settings.host, help="Bind address")
@click.option("--port", default=settings.port, type=int, help="Bind port")
@click.option("--shell", default=settings.shell, help="Shell to spawn")
@click.option("--cmd", default="", help="Command to run instead of shell (e.g. 'htop')")
@click.option("--debug", is_flag=True, default=settings.debug, help="Debug mode")
@click.option("--log-dir", default=str(settings.log_dir), help="Session log directory")
@click.option("--no-log", is_flag=True, default=False, help="Disable session logging")
@click.option("--unsecure", is_flag=True, default=settings.unsecure, help="Run without SSL")
@click.option("--ssl-dir", default=str(settings.ssl_dir), help="SSL certificate directory")
@click.option(
    "--generate-certs", is_flag=True, default=False,
    help="Generate SSL certificates and exit",
)
@click.option("--theme", default=settings.theme, help="Color theme (default/dracula/nord/...)")
@click.option(
    "--motd-art", default=settings.motd_art,
    help="MOTD banner: 'butterfly', 'none', or path to custom file",
)
def main(
    host: str,
    port: int,
    shell: str,
    cmd: str,
    debug: bool,
    log_dir: str,
    no_log: bool,
    unsecure: bool,
    ssl_dir: str,
    generate_certs: bool,
    theme: str,
    motd_art: str,
) -> None:
    """Butterfly — Async web terminal emulator."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    settings.host = host
    settings.port = port
    settings.shell = shell
    settings.cmd = cmd
    settings.debug = debug
    settings.log_dir = Path(log_dir)
    settings.log_enabled = not no_log
    settings.unsecure = unsecure
    settings.ssl_dir = Path(ssl_dir)
    settings.theme = theme
    settings.motd_art = motd_art

    # --- Certificate generation mode ---
    if generate_certs:
        from butterfly.ssl_certs import prepare_ssl_certs

        prepare_ssl_certs(settings.ssl_dir, host)
        logger.info("Certificates ready in %s", settings.ssl_dir)
        sys.exit(0)

    # --- Build uvicorn kwargs ---
    uvicorn_kwargs: dict = {
        "host": host,
        "port": port,
        "log_level": "debug" if debug else "info",
        "ws": "websockets",
    }

    if not unsecure:
        from butterfly.ssl_certs import get_ssl_paths

        ssl_opts = get_ssl_paths(settings.ssl_dir, host)
        if ssl_opts:
            uvicorn_kwargs.update(ssl_opts)
            proto = "https"
        else:
            logger.warning(
                "SSL certificates not found in %s. "
                "Run with --generate-certs --host=%s to create them, "
                "or use --unsecure to skip SSL.",
                settings.ssl_dir,
                host,
            )
            sys.exit(1)
    else:
        proto = "http"

    logger.info("Butterfly starting at %s://%s:%d", proto, host, port)
    uvicorn.run("butterfly.app:app", **uvicorn_kwargs)
