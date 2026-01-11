"""
Logging configuration for CatchSnapWeb Traffic Recorder
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logs"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add exception information
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }

        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data['data'] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """Console formatter with colors for better readability"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']

        # Format log message
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level_colored = f"{color}{record.levelname:8s}{reset}"

        message = f"[{timestamp}] {level_colored} {record.getMessage()}"

        # Add exception info
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    console_output: bool = True,
    file_output: bool = True,
    log_dir: Optional[Path] = None,
    log_rotation_size: int = 50  # MB
) -> logging.Logger:
    """
    Sets up the logging system

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format ("json" or "text")
        console_output: Output to console
        file_output: Output to file
        log_dir: Directory for log files
        log_rotation_size: Maximum log file size in MB

    Returns:
        Configured logger
    """
    # Create root logger
    logger = logging.getLogger('catchsnap')
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        if log_format == "json":
            console_handler.setFormatter(JsonFormatter())
        else:
            console_handler.setFormatter(ColoredConsoleFormatter())

        logger.addHandler(console_handler)

    # File handler
    if file_output and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main log file with rotation
        log_file = log_dir / "catchsnap.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_rotation_size * 1024 * 1024,  # MB to bytes
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))

        if log_format == "json":
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))

        logger.addHandler(file_handler)

        # Separate error log file
        error_log_file = log_dir / "errors.log"
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=log_rotation_size * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)

        if log_format == "json":
            error_handler.setFormatter(JsonFormatter())
        else:
            error_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d'
            ))

        logger.addHandler(error_handler)

    return logger


class StructuredLogger:
    """Wrapper for structured logs with extra_data support"""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, msg: str, extra_data: dict = None, **kwargs):
        """Internal log with extra_data support"""
        if extra_data:
            kwargs['extra'] = {'extra_data': extra_data}
        self._logger.log(level, msg, **kwargs)

    def debug(self, msg: str, extra_data: dict = None, **kwargs):
        self._log(logging.DEBUG, msg, extra_data, **kwargs)

    def info(self, msg: str, extra_data: dict = None, **kwargs):
        self._log(logging.INFO, msg, extra_data, **kwargs)

    def warning(self, msg: str, extra_data: dict = None, **kwargs):
        self._log(logging.WARNING, msg, extra_data, **kwargs)

    def error(self, msg: str, extra_data: dict = None, **kwargs):
        self._log(logging.ERROR, msg, extra_data, **kwargs)

    def critical(self, msg: str, extra_data: dict = None, **kwargs):
        self._log(logging.CRITICAL, msg, extra_data, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Gets a structured logger with the given name"""
    logger = logging.getLogger(f'catchsnap.{name}')
    return StructuredLogger(logger)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for context-aware logs"""

    def process(self, msg: str, kwargs: dict) -> tuple:
        # Add extra_data if present
        if 'extra_data' in kwargs:
            extra = kwargs.get('extra', {})
            extra['extra_data'] = kwargs.pop('extra_data')
            kwargs['extra'] = extra
        return msg, kwargs


def get_context_logger(name: str, context: Dict[str, Any]) -> LoggerAdapter:
    """
    Creates a logger with context information

    Args:
        name: Logger name
        context: Context data (e.g., session_id, browser)

    Returns:
        Logger with context
    """
    logger = get_logger(name)
    return LoggerAdapter(logger, context)
