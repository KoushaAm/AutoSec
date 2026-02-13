# Pipeline/__init__.py
"""
Entry point package for the LangGraph Pipeline
"""
import logging

# Custom formatter to create block-style logs
class BlockFormatter(logging.Formatter):
    def format(self, record) -> str:
        # Header WITHOUT the message
        header = super().format(record)  # uses fmt without %(message)s
        msg = record.getMessage()
        top = f"===== {header}:{msg} ====="
        return top


# package-level logger (for everything under Pipeline.*)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False  # prevent duplicate root logging

if not logger.handlers:
    handler = logging.StreamHandler()

    # NOTE: no %(message)s here - message is handled by BlockFormatter body
    fmt = "%(asctime)s - %(name)s:%(levelname)s"
    handler.setFormatter(BlockFormatter(fmt))

    logger.addHandler(handler)

# ========= package exports =========
from .pipeline import (
    pipeline_main,
)

__all__ = [
    "pipeline_main",
]
