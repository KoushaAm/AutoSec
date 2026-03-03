import logging
from pathlib import Path
from typing import Optional

_LOGGER_NAMESPACE = "patcher"


def _clear_handlers(logger: logging.Logger) -> None:
    # Avoid duplicate logs if setup is called multiple times in the same process
    if logger.handlers:
        logger.handlers.clear()


def _make_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_run_logger(output_dir: Path, level: str = "INFO") -> logging.Logger:
    """
    Creates the run logger:
      - logs to console
      - logs to output/logs/run.log
    """
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"{_LOGGER_NAMESPACE}.run")
    logger.setLevel(level.upper())
    logger.propagate = False

    _clear_handlers(logger)
    formatter = _make_formatter()

    # Console
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # File
    fh = logging.FileHandler(logs_dir / "run.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


def get_patch_logger(
    output_dir: Path,
    patch_id: str,
    level: str = "INFO",
    *,
    also_log_to_run: Optional[logging.Logger] = None,
) -> logging.Logger:
    """
    Creates/returns a per-patch logger:
      - logs to console
      - logs to output/logs/patch_<patch_id>.log

    If also_log_to_run is passed, it will additionally emit to the run log handlers.
    (Off by default to keep patch logs isolated.)
    """
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    safe_id = "".join(c for c in patch_id if c.isalnum() or c in ("-", "_"))
    logger_name = f"{_LOGGER_NAMESPACE}.patch.{safe_id}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(level.upper())
    logger.propagate = False

    _clear_handlers(logger)
    formatter = _make_formatter()

    # Console
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # Patch file
    fh = logging.FileHandler(logs_dir / f"patch_{safe_id}.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Optional duplication into run logger's handlers
    if also_log_to_run is not None:
        for h in also_log_to_run.handlers:
            logger.addHandler(h)

    return logger