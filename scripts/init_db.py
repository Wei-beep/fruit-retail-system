import _bootstrap  # noqa: F401

from app.db.init_db import initialize_database


def main() -> None:
    initialize_database()
    print("Database initialized.")


if __name__ == "__main__":
    main()
