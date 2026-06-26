
from **future** import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Union

DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger(
log_dir: str = "logs",
log_file: str = "modinteractive.log",
level: Union[str, int] = "INFO",
max_bytes: int = 5_242_880,
backup_count: int = 3,
) -> logging.Logger:
numeric_level = _resolve_log_level(level)

logger = logging.getLogger("modInteractive")
logger.setLevel(numeric_level)
logger.propagate = False

_clear_handlers(logger)

formatter = logging.Formatter(
    fmt=DEFAULT_LOG_FORMAT,
    datefmt=DEFAULT_DATE_FORMAT,
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(numeric_level)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

log_path = _prepare_log_path(log_dir, log_file)

if log_path is not None:
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max(1024, int(max_bytes)),
            backupCount=max(0, int(backup_count)),
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("Cannot create log file %s: %s", log_path, exc)

_configure_noisy_loggers()

logger.debug(
    "Logger configured: level=%s, log_dir=%s, log_file=%s",
    logging.getLevelName(numeric_level),
    log_dir,
    log_file,
)

return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:

if not name:
    return logging.getLogger("modInteractive")

clean_name = str(name).strip()

if not clean_name:
    return logging.getLogger("modInteractive")

if clean_name.startswith("modInteractive"):
    return logging.getLogger(clean_name)

return logging.getLogger(f"modInteractive.{clean_name}")


def _resolve_log_level(level: Union[str, int]) -> int:

if isinstance(level, int):
    return level

level_name = str(level or "INFO").upper().strip()
numeric_level = getattr(logging, level_name, None)

if isinstance(numeric_level, int):
    return numeric_level

return logging.INFO


def _prepare_log_path(log_dir: str, log_file: str) -> Optional[Path]:

try:
    directory = Path(log_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / log_file
except OSError as exc:
    print(
        f"WARNING: Cannot create log directory {log_dir}: {exc}",
        file=sys.stderr,
    )
    return None


def _clear_handlers(logger: logging.Logger) -> None:

for handler in list(logger.handlers):
    logger.removeHandler(handler)

    try:
        handler.close()
    except Exception:
        pass
```

def _configure_noisy_loggers() -> None:
noisy_loggers = (
"werkzeug",
"flask",
"urllib3",
"PIL",
"matplotlib",
"ultralytics",
"cv2",
)

for logger_name in noisy_loggers:
    logging.getLogger(logger_name).setLevel(logging.WARNING)
