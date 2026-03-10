from __future__ import annotations

import logging
import sys

import requests

from app.config import AppConfig
from app.dokploy_client import DokployClient
from app.sync_service import SyncService


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def main() -> int:
    try:
        config = AppConfig.from_env()
        configure_logging(config.log_level)

        client = DokployClient(config)
        service = SyncService(config, client)
        service.run()

        logging.getLogger(__name__).info("Edge sync completed successfully")
        return 0

    except requests.HTTPError as exc:
        logging.getLogger(__name__).error(
            "HTTP error: %s | body=%s",
            exc,
            getattr(exc.response, "text", ""),
        )
        return 1

    except KeyError as exc:
        logging.getLogger(__name__).error("Missing required environment variable: %s", exc)
        return 1

    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).exception("Unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())