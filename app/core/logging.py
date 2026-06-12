"""
Structured Logging Configuration using Loguru
"""
import sys
from loguru import logger
from app.core.config import settings

def setup_logging():
    # Remove default handler
    logger.remove()
    
    # Add console handler with structured format if not debug, else readable format
    if settings.DEBUG:
        logger.add(
            sys.stdout, 
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG"
        )
    else:
        # JSON structured logging for production (e.g., Sentry, Datadog)
        logger.add(sys.stdout, format="{message}", level="INFO", serialize=True)

    logger.info("Logging initialized.")
