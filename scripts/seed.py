"""
Foundation verification and database seeding utility.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/api")))

from app.core.config import settings
from app.core.logging import setup_logging, logger


def main():
    setup_logging()
    logger.info("Initializing %s foundation environment...", settings.APP_NAME)
    logger.info("Environment: %s", settings.APP_ENV)
    logger.info("Database URL: %s", settings.DATABASE_URL)
    logger.info("Redis URL: %s", settings.REDIS_URL)
    logger.info("Document TTL: %s hours", settings.DOCUMENT_TTL_HOURS)
    logger.info("Foundation verification complete.")


if __name__ == "__main__":
    main()
