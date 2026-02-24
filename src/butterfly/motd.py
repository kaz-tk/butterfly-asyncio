"""Message of the Day — ASCII art banner.

Displayed to clients on new session connection.
Butterfly art based on the original motd by Florian Mounier.

The MOTD can be customized via:
  --motd-art butterfly   Built-in butterfly ASCII art (default)
  --motd-art none        No banner
  --motd-art /path/file  Custom file (may contain ANSI escape codes)
"""

from pathlib import Path

from butterfly import __version__
from butterfly.config import settings

# ANSI color codes
BLUE = "\x1b[34m"
WHITE = "\x1b[37m"
BRIGHT_WHITE = "\x1b[97m"
YELLOW = "\x1b[33m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
RESET = "\x1b[0m"

BUTTERFLY_ART = f"""\
{BLUE}                   `         '
   ;,,,             `       '             ,,,;
   `Y888888bo.       :     :       .od888888Y'
     8888888888b.     :   :     .d8888888888
     88888Y'  `Y8b.   `   '   .d8Y'  `Y88888
    j88888  {WHITE}.db.{BLUE}  Yb. '   ' .dY  {WHITE}.db.{BLUE}  88888k
      `888  {WHITE}Y88Y{BLUE}    `b ( ) d'    {WHITE}Y88Y{BLUE}  888'
       888b  {WHITE}'"{BLUE}        ,',        {WHITE}"'{BLUE}  d888
      j888888bd8gf"'   ':'   `"?g8bd888888k
        {WHITE}'Y'{BLUE}   .8'     d' 'b     '8.   {WHITE}'Y'{RESET}
         {WHITE}!{BLUE}   .8' {WHITE}db{BLUE}  d'; ;`b  {WHITE}db{BLUE} '8.   {WHITE}!{BLUE}
            d88  {WHITE}`'{BLUE}  8 ; ; 8  {WHITE}`'{BLUE}  88b        {WHITE}butterfly {YELLOW}v{__version__}{BLUE}
           d888b   .g8 ',' 8g.   d888b
          :888888888Y'     'Y888888888:
          '! 8888888'       `8888888 !'
             '8Y  {WHITE}`Y         Y'{BLUE}  Y8'
{WHITE}              Y                   Y
              !                   !{RESET}
"""


def _load_art() -> str:
    """Load ASCII art based on config.

    Returns:
        - Built-in butterfly art if motd_art == "butterfly"
        - Empty string if motd_art == "none"
        - File contents if motd_art is a path to an existing file
        - Built-in butterfly art as fallback
    """
    art_name = settings.motd_art

    if art_name == "none":
        return ""

    if art_name == "butterfly":
        return BUTTERFLY_ART

    # Treat as file path
    path = Path(art_name)
    if path.is_file():
        return path.read_text()

    # Fallback
    return BUTTERFLY_ART


def render_motd(host: str, port: int, remote_addr: str = "") -> bytes:
    """Render the MOTD banner with connection info."""
    art = _load_art()

    # Skip entirely if no art and no info needed
    if not art and settings.motd_art == "none":
        return b""

    secure = not settings.unsecure
    proto = "https" if secure else "http"
    color = GREEN if secure else RED
    mode = "secure" if secure else "UNSECURE"

    # Replace \n with \r\n in art (raw PTY needs carriage return)
    if art:
        art = art.replace("\r\n", "\n").replace("\n", "\r\n")
    lines = [art] if art else []
    lines.append(f"  {BRIGHT_WHITE}Listening on:{RESET}  {color}{proto}://{host}:{port}{RESET}")
    if remote_addr:
        lines.append(f"  {BRIGHT_WHITE}Connected from:{RESET} {color}{remote_addr}{RESET}")
    lines.append(f"  {BRIGHT_WHITE}Mode:{RESET}           {color}{mode}{RESET}")
    lines.append("")

    if not secure:
        lines.append(f"  {RED}/!\\ This session is UNSECURE.{RESET}")
        lines.append("")

    lines.append("")

    return "\r\n".join(lines).encode()
