"""Butterfly configuration via Pydantic Settings."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings

# Config directory (XDG compliant)
if os.getuid() == 0:
    _xdg = os.getenv("XDG_CONFIG_DIRS", "/etc")
else:
    _xdg = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))

BUTTERFLY_DIR = Path(_xdg) / "butterfly"
SSL_DIR = BUTTERFLY_DIR / "ssl"


class Settings(BaseSettings):
    model_config = {"env_prefix": "BUTTERFLY_"}

    host: str = "0.0.0.0"
    port: int = 57575
    shell: str = "/bin/bash"
    debug: bool = False

    # Command (run instead of shell, e.g. "htop" or "ls -la")
    cmd: str = ""

    # Terminal
    term: str = "xterm-256color"
    default_cols: int = 80
    default_rows: int = 24
    history_size: int = 50_000

    # Appearance
    theme: str = "default"  # xterm.js color theme (default/dracula/solarized-dark/...)
    motd_art: str = "butterfly"  # MOTD: "butterfly", "none", or file path

    # Session logging (script/scriptreplay compatible)
    log_enabled: bool = True
    log_dir: Path = Path("logs")

    # WebSocket
    keepalive_interval: int = 30

    # SSL / TLS
    unsecure: bool = False
    ssl_dir: Path = SSL_DIR

    # URI prefix (for reverse proxy)
    uri_root_path: str = ""


settings = Settings()
