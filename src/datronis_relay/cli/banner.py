"""ASCII art banner for terminal output."""

from __future__ import annotations

from datronis_relay import __version__

# ANSI escape codes for dark green color.
_GREEN = "\033[38;5;28m"  # dark green (256-color)
_DIM = "\033[2m"          # dim for the border
_BOLD = "\033[1m"         # bold for the logo
_RESET = "\033[0m"

# Box-drawing characters for clean borders.
_TL = "\u256d"  # ╭
_TR = "\u256e"  # ╮
_BL = "\u2570"  # ╰
_BR = "\u256f"  # ╯
_H = "\u2500"   # ─
_V = "\u2502"   # │

_LOGO_LINES = [
    r" ██████╗  █████╗ ████████╗██████╗  ██████╗ ███╗   ██╗██╗███████╗",
    r" ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║██║██╔════╝",
    r" ██║  ██║███████║   ██║   ██████╔╝██║   ██║██╔██╗ ██║██║███████╗",
    r" ██║  ██║██╔══██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║██║╚════██║",
    r" ██████╔╝██║  ██║   ██║   ██║  ██║╚██████╔╝██║ ╚████║██║███████║",
    r" ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝╚══════╝",
    "",
    r" ██████╗ ███████╗██╗      █████╗ ██╗   ██╗",
    r" ██╔══██╗██╔════╝██║     ██╔══██╗╚██╗ ██╔╝",
    r" ██████╔╝█████╗  ██║     ███████║ ╚████╔╝",
    r" ██╔══██╗██╔══╝  ██║     ██╔══██║  ╚██╔╝",
    r" ██║  ██║███████╗███████╗██║  ██║   ██║",
    r" ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝",
]

_TAGLINE = "self-hosted chat bridge for operators · secure · terminal-first"

_BOX_WIDTH = 78


def _pad(text: str, *, color: bool = True) -> str:
    """Pad text inside the box frame."""
    inner = _BOX_WIDTH - 2  # subtract the two │ chars
    content = f"{text:<{inner - 1}}"
    if color:
        border = f"{_DIM}{_GREEN}{_V}{_RESET}"
        return f"{border} {_BOLD}{_GREEN}{content}{_RESET}{border}"
    return f"{_V} {content}{_V}"


def banner(*, subtitle: str = "", color: bool = True) -> str:
    """Return the full bordered banner string."""
    if color:
        border_style = f"{_DIM}{_GREEN}"
        top = f"{border_style}{_TL}{_H * (_BOX_WIDTH - 2)}{_TR}{_RESET}"
        bot = f"{border_style}{_BL}{_H * (_BOX_WIDTH - 2)}{_BR}{_RESET}"
    else:
        top = f"{_TL}{_H * (_BOX_WIDTH - 2)}{_TR}"
        bot = f"{_BL}{_H * (_BOX_WIDTH - 2)}{_BR}"

    lines = [top]
    for logo_line in _LOGO_LINES:
        lines.append(_pad(logo_line, color=color))
    lines.append(_pad("", color=color))
    lines.append(_pad(_TAGLINE, color=color))
    if subtitle:
        lines.append(_pad(subtitle, color=color))
    lines.append(_pad(f"v{__version__}", color=color))
    lines.append(bot)
    return "\n".join(lines)


def print_banner(*, subtitle: str = "") -> None:
    """Print the banner to stdout."""
    print(banner(subtitle=subtitle))
