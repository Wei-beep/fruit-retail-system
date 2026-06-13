from __future__ import annotations

import os
from pathlib import Path


def configure_gui_display(gui_config: dict) -> None:
    """Prepare display-related environment variables for Raspberry Pi GUI use.

    When the program is launched from an SSH shell on the same Raspberry Pi,
    DISPLAY is often absent even though the DSI screen is active. In that case
    Tkinter can usually open on the local desktop through :0.
    """
    if not gui_config.get("auto_set_display", False):
        return

    os.environ.setdefault("DISPLAY", str(gui_config.get("display", ":0")))

    runtime_dir = Path("/run/user/1000")
    if runtime_dir.exists():
        os.environ.setdefault("XDG_RUNTIME_DIR", str(runtime_dir))

    xauthority = Path.home() / ".Xauthority"
    if xauthority.exists():
        os.environ.setdefault("XAUTHORITY", str(xauthority))
