import os
import sys

# 保证从任意工作目录运行 `python main.py` 都能导入 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.main_window import run_gui


def main() -> None:
    run_gui()


if __name__ == "__main__":
    main()
