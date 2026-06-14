import _bootstrap  # noqa: F401

from app.web.launcher import run_web


def main() -> None:
    run_web()


if __name__ == "__main__":
    main()
