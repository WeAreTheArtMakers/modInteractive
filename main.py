from **future** import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from types import FrameType
from typing import Optional

PROJECT_ROOT = Path(**file**).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
sys.path.insert(0, str(PROJECT_ROOT))

from app import Application
from core.config import Config
from core.healthcheck import HealthCheck
from core.logger import setup_logger

APP_NAME = "modInteractive"
APP_VERSION = "1.0.0"
DEFAULT_CONFIG = "config.json"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "modinteractive.log"

def parse_args() -> argparse.Namespace:
parser = argparse.ArgumentParser(
description="modInteractive - Motion Triggered HDMI Video Display for Raspberry Pi"
)

```
parser.add_argument(
    "--check",
    action="store_true",
    help="Run system health check and exit",
)

parser.add_argument(
    "--config",
    type=str,
    default=DEFAULT_CONFIG,
    help=f"Path to configuration file (default: {DEFAULT_CONFIG})",
)

parser.add_argument(
    "--log-level",
    type=str,
    default=None,
    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    help="Override log level from config",
)

return parser.parse_args()
```

def resolve_path(path_value: str) -> Path:
path = Path(path_value).expanduser()

```
if not path.is_absolute():
    path = PROJECT_ROOT / path

return path.resolve()
```

def ensure_runtime_directories() -> None:
for directory in ("logs", "videos"):
(PROJECT_ROOT / directory).mkdir(parents=True, exist_ok=True)

def load_log_level(config_path: Path, cli_level: Optional[str]) -> str:
if cli_level:
return cli_level.upper()

```
try:
    config = Config(str(config_path))
    config.load()
    return str(config.get("system.log_level", "INFO")).upper()
except Exception:
    return "INFO"
```

def configure_logging(config_path: Path, cli_level: Optional[str]) -> logging.Logger:
ensure_runtime_directories()

```
return setup_logger(
    log_dir=str(PROJECT_ROOT / DEFAULT_LOG_DIR),
    log_file=DEFAULT_LOG_FILE,
    level=load_log_level(config_path, cli_level),
)
```

def run_health_check(config_path: Path, logger: logging.Logger) -> int:
logger.info("Running system health check with config: %s", config_path)

```
try:
    config = Config(str(config_path))
    config.load()

    check = HealthCheck(config)
    check.run_all()
    check.print_report()

    if hasattr(check, "exit_code"):
        return int(check.exit_code())

    return 1 if any(status == "FAIL" for status, _name, _detail in check.results) else 0

except KeyboardInterrupt:
    logger.info("Health check interrupted")
    return 130
except Exception:
    logger.exception("Health check failed")
    return 1
```

async def run_application(config_path: Path, logger: logging.Logger) -> int:
app = Application(config_path=str(config_path))
stop_event = asyncio.Event()
loop = asyncio.get_running_loop()

```
def request_shutdown(signum: int) -> None:
    logger.info("Signal %d received, shutting down...", signum)
    app.stop()
    stop_event.set()

def sync_signal_handler(signum: int, _frame: Optional[FrameType]) -> None:
    loop.call_soon_threadsafe(request_shutdown, signum)

for sig in (signal.SIGINT, signal.SIGTERM):
    try:
        loop.add_signal_handler(sig, request_shutdown, sig)
    except NotImplementedError:
        signal.signal(sig, sync_signal_handler)

app_task = asyncio.create_task(app.run(), name="modinteractive-app")
stop_task = asyncio.create_task(stop_event.wait(), name="modinteractive-stop")

try:
    done, pending = await asyncio.wait(
        {app_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stop_task in done:
        app.stop()

        if not app_task.done():
            await app_task

    if app_task.done():
        if app_task.cancelled():
            logger.info("Application task cancelled")
            return 130

        exception = app_task.exception()

        if exception is not None:
            logger.error("Application task failed: %s", exception, exc_info=exception)
            return 1

    for task in pending:
        task.cancel()

    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    return 0

except KeyboardInterrupt:
    logger.info("Keyboard interrupt received")
    app.stop()
    return 130
except asyncio.CancelledError:
    logger.info("Main task cancelled")
    app.stop()
    raise
except Exception:
    logger.exception("Fatal error in main loop")
    app.stop()
    return 1
finally:
    if not stop_task.done():
        stop_task.cancel()
        await asyncio.gather(stop_task, return_exceptions=True)

    await app.shutdown()
```

def main() -> None:
args = parse_args()
config_path = resolve_path(args.config)
logger = configure_logging(config_path, args.log_level)

```
logger.info("=" * 60)
logger.info("%s v%s - Motion Triggered HDMI Video Display", APP_NAME, APP_VERSION)
logger.info("=" * 60)
logger.info("Project root: %s", PROJECT_ROOT)
logger.info("Config path: %s", config_path)

if args.check:
    raise SystemExit(run_health_check(config_path, logger))

try:
    exit_code = asyncio.run(run_application(config_path, logger))
except KeyboardInterrupt:
    logger.info("Keyboard interrupt received before shutdown completed")
    exit_code = 130
except Exception:
    logger.exception("Unhandled fatal error")
    exit_code = 1

logger.info("Application exited with code %d", exit_code)
raise SystemExit(exit_code)
```

if **name** == "**main**":
main()
