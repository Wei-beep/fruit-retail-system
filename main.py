import os
import sys

# 保证从任意工作目录运行 `python main.py` 都能导入 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import load_config


def main() -> None:
    # 按 config.yaml 的 gui.frontend 选择前端：web(默认 Chromium kiosk) 或 tk(旧 Tkinter)
    frontend = load_config().get("gui", {}).get("frontend", "web")
    if frontend == "tk":
        from app.gui.main_window import run_gui
        run_gui()
    else:
        from app.web.launcher import run_web
        run_web()


if __name__ == "__main__":
    main()
