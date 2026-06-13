import _bootstrap  # noqa: F401

import uvicorn

from app.core.config import load_config


def main() -> None:
    config = load_config()
    uvicorn.run(
        "app.api.server:app",
        host=config["api"]["host"],
        port=int(config["api"]["port"]),
        reload=False,
    )


if __name__ == "__main__":
    main()
