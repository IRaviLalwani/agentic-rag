from __future__ import annotations

import logging
from pathlib import Path

from path_config import get_error_log_file, get_log_dir

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    error_file_handler = logging.FileHandler(get_error_log_file(), encoding="utf-8")
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(error_file_handler)

    return logger
