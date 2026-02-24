# Butterfly 4.0

A modern async web terminal emulator built with FastAPI(asyncio) + xterm.js.

This is a complete rewrite of [Butterfly](https://github.com/paradoxxxzero/butterfly) by [Florian Mounier](http://paradoxxxzero.github.io/), replacing Tornado with asyncio/FastAPI and the custom CoffeeScript terminal with xterm.js.

## What Changed from 3.x

| Layer     | Butterfly 3.x              | Butterfly 4.0                        |
| --------- | -------------------------- | ------------------------------------ |
| Backend   | Tornado                    | FastAPI + uvicorn                    |
| Frontend  | CoffeeScript (5000+ LOC)   | xterm.js (CDN)                       |
| PTY I/O   | `ioloop.add_handler()`     | `asyncio.add_reader()`               |
| Config    | `tornado.options`          | Pydantic Settings + click            |
| Logging   | 50KB history only          | script(1)/scriptreplay(1) compatible |
| Auth      | X.509, PAM                 | None (proxy-based)                   |
| Package   | setup.py + bower + grunt   | pyproject.toml + uv                  |
| Python    | 2/3 compat                 | 3.12+                                |
| WebSocket | 2 connections (ctl + data) | 1 connection (binary + JSON)         |

## Architecture

```
src/butterfly/
├── __init__.py          # Version
├── __main__.py          # python -m butterfly
├── app.py               # FastAPI app factory + lifespan
├── config.py            # Pydantic Settings (BUTTERFLY_* env vars)
├── cli.py               # click CLI entry point
├── pty_manager.py       # asyncio PTY (fork, add_reader, resize)
├── motd.py              # MOTD banner (built-in or custom file)
├── themes.py            # xterm.js color themes (6 built-in)
├── ssl_certs.py         # SSL certificate generation (openssl CLI)
├── session_logger.py    # script(1)/scriptreplay(1) compatible logging
├── session.py           # SessionManager + TerminalSession
├── websocket.py         # WebSocket handler (single connection)
├── routes.py            # HTTP routes + theme API
└── static/
    ├── index.html       # xterm.js terminal page (CDN)
    ├── css/terminal.css # Fullscreen terminal styling
    └── js/terminal.js   # xterm.js WebSocket client
```

### WebSocket Protocol (Single Connection)

| Direction        | Frame Type | Content                                                      |
| ---------------- | ---------- | ------------------------------------------------------------ |
| client -> server | Binary     | Raw terminal input                                           |
| client -> server | Text       | JSON `{"type": "resize", "cols": N, "rows": N}`              |
| server -> client | Binary     | Raw terminal output                                          |
| server -> client | Text       | JSON `{"type": "session", "id": "..."}` / `{"type": "exit"}` |

### PTY Management

- `pty.fork()` for PTY creation
- `fcntl` O_NONBLOCK for non-blocking I/O
- `asyncio.get_running_loop().add_reader(fd, callback)` for zero-latency reads
- `TIOCSWINSZ` ioctl for resize
- `SIGHUP` + `SIGCONT` + `waitpid` for clean shutdown

### Session Features

- Multi-client: multiple browser tabs can share the same PTY session
- History buffer (50KB): reconnecting clients receive replay of recent output
- Auto-cleanup: sessions are removed when PTY exits and all clients disconnect
- MOTD: customizable banner on connect (`--motd-art butterfly`, custom file path, or `none`)
- Themes: 6 built-in xterm.js color themes, switchable via Alt+T or `--theme`
- Session list: **Alt+S** to browse active sessions, switch between them, or create new ones
- Per-session command override via `?cmd=htop` query parameter
- `--cmd` flag to globally replace the default shell with a command

## Quick Start

```bash
uv sync
uv run butterfly --unsecure --debug
```

Open <http://localhost:57575> in your browser.

## SSL / TLS

By default Butterfly runs in secure mode (SSL required). Use `--unsecure` to skip SSL, or generate certificates:

```bash
# Generate self-signed CA + server certificate
uv run butterfly --generate-certs --host=myhost.example.com

# Run with SSL (default)
uv run butterfly --host=myhost.example.com

# Run without SSL
uv run butterfly --unsecure
```

Certificates are stored in `~/.config/butterfly/ssl/` (or `/etc/butterfly/ssl/` for root):

```text
butterfly_ca.crt / butterfly_ca.key          — Self-signed CA
butterfly_<host>.crt / butterfly_<host>.key  — Server certificate (signed by CA)
```

## CLI Options

```bash
uv run butterfly --help
uv run butterfly --host 0.0.0.0 --port 8080
uv run butterfly --shell /bin/zsh
uv run butterfly --cmd htop            # Run command instead of shell
uv run butterfly --unsecure            # Run without SSL
uv run butterfly --generate-certs      # Generate certs and exit
uv run butterfly --ssl-dir /path/to/certs
uv run butterfly --theme dracula        # Color theme
uv run butterfly --motd-art /path/to/banner.txt  # Custom MOTD file
uv run butterfly --motd-art none       # No banner
uv run butterfly --no-log              # Disable session logging
uv run butterfly --log-dir /tmp/sessions
```

### Alternative: uvicorn direct

Environment variables (`BUTTERFLY_*`) are used for configuration:

```bash
BUTTERFLY_UNSECURE=true \
  uvicorn butterfly.app:app --host 0.0.0.0 --port 57575
```

## Themes

6 built-in color themes: `default`, `dracula`, `solarized-dark`, `solarized-light`, `monokai`, `nord`, `aether`

- **Alt+T** in the terminal to open the theme picker
- `--theme <name>` to set the server default
- Theme selection is saved in localStorage per browser

### Theme API

```bash
curl /api/themes              # List available themes
curl /api/themes/dracula      # Get specific theme colors
```

## Session Logging

Terminal sessions are recorded in script(1)/scriptreplay(1) compatible format:

```
logs/
└── 2026/02/24/
    ├── typescript-a1b2c3d4-x9y8z7    # Raw output
    └── typescript-a1b2c3d4-x9y8z7.timing  # Timing data
```

Replay with:

```bash
scriptreplay --timing=<file>.timing <file>
```

## Docker

```bash
docker build -t butterfly .
docker run -p 57575:57575 butterfly
```

## Development

```bash
make install     # uv sync
make lint        # ruff check
make fmt         # ruff format + fix
make run-debug   # Run with debug logging
```

## Credits

Butterfly was originally created by [Florian Mounier (paradoxxxzero)](https://github.com/paradoxxxzero/butterfly). This 4.0 rewrite preserves the spirit of the original while modernizing the stack.

## License

```
Butterfly Copyright (C) 2015-2017  Florian Mounier
Butterfly 4.0 Copyright (C) 2026-  Kazushige Takeuchi

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
```
