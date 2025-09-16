"""
Modular logging utility for DisparaAI.
Provides structured logging with different levels and consistent formatting.
"""

import logging
import logging.handlers
import json
import os
import sys
import re
from datetime import datetime
from typing import Optional, Dict, Any, Union
from pathlib import Path


def sanitize_base64_data(data: Union[str, Dict, Any], max_length: int = 100) -> Union[str, Dict, Any]:
    """
    Sanitize base64 data in logs by truncating long base64 strings.
    
    Args:
        data: Data to sanitize (string, dict, or other)
        max_length: Maximum length for base64 strings in logs
    
    Returns:
        Sanitized data with base64 strings truncated
    """
    if isinstance(data, str):
        # Check if it looks like base64 data (long string with base64 chars)
        if len(data) > max_length and re.match(r'^[A-Za-z0-9+/=]+$', data):
            return f"<base64 data: {len(data)} chars - {data[:20]}...{data[-10:]}>"
        return data
    
    elif isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Sanitize known base64 fields
            if key in ('base64', 'mediaBase64', 'file_data', 'image_data', 'content') and isinstance(value, str):
                if len(value) > max_length:
                    sanitized[key] = f"<base64 data: {len(value)} chars - {value[:20]}...{value[-10:]}>"
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = sanitize_base64_data(value, max_length)
        return sanitized
    
    elif isinstance(data, (list, tuple)):
        return [sanitize_base64_data(item, max_length) for item in data]
    
    return data


def safe_json_dumps(data: Any, indent: Optional[int] = None, max_base64_length: int = 100) -> str:
    """
    JSON dumps with base64 data sanitization to prevent log pollution.
    
    Args:
        data: Data to serialize
        indent: JSON indentation
        max_base64_length: Maximum length for base64 strings in output
    
    Returns:
        JSON string with sanitized base64 data
    """
    sanitized_data = sanitize_base64_data(data, max_base64_length)
    return json.dumps(sanitized_data, indent=indent, default=str)


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'levelname', 'levelno', 
                          'pathname', 'filename', 'module', 'lineno', 
                          'funcName', 'created', 'msecs', 'relativeCreated', 
                          'thread', 'threadName', 'processName', 'process',
                          'exc_info', 'exc_text', 'stack_info', 'getMessage'):
                log_data[key] = value
        
        return json.dumps(log_data)


class SimpleFormatter(logging.Formatter):
    """Simple formatter for console output."""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def get_logger(name: str, 
               level: Optional[str] = None,
               use_json: bool = False,
               log_file: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically module name)
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        use_json: Whether to use structured JSON logging
        log_file: Optional log file path
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if already configured
    if logger.handlers:
        return logger
    
    # Set level from parameter, environment, or default
    log_level = (level or 
                os.getenv('LOG_LEVEL', 'INFO')).upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if use_json or os.getenv('LOG_FORMAT', '').lower() == 'json':
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(SimpleFormatter())
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file or os.getenv('LOG_FILE'):
        file_path = log_file or os.getenv('LOG_FILE')
        log_dir = Path(file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        
        if use_json or os.getenv('LOG_FORMAT', '').lower() == 'json':
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(SimpleFormatter())
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def setup_logging(level: str = 'INFO',
                 use_json: bool = False,
                 log_file: Optional[str] = None) -> None:
    """
    Setup global logging configuration.
    
    Args:
        level: Default log level
        use_json: Whether to use structured JSON logging
        log_file: Optional log file path
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure root logger
    log_level = os.getenv('LOG_LEVEL', level).upper()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if use_json or os.getenv('LOG_FORMAT', '').lower() == 'json':
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(SimpleFormatter())
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file or os.getenv('LOG_FILE'):
        file_path = log_file or os.getenv('LOG_FILE')
        log_dir = Path(file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        
        if use_json or os.getenv('LOG_FORMAT', '').lower() == 'json':
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(SimpleFormatter())
        root_logger.addHandler(file_handler)


# Convenience functions for different log levels
def debug(message: str, extra: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log debug message."""
    logger = get_logger(logger_name)
    logger.debug(message, extra=extra or {})


def info(message: str, extra: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log info message."""
    logger = get_logger(logger_name)
    logger.info(message, extra=extra or {})


def warning(message: str, extra: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log warning message."""
    logger = get_logger(logger_name)
    logger.warning(message, extra=extra or {})


def error(message: str, extra: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log error message."""
    logger = get_logger(logger_name)
    logger.error(message, extra=extra or {})


def critical(message: str, extra: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log critical message."""
    logger = get_logger(logger_name)
    logger.critical(message, extra=extra or {})


def safe_info(message: str, data: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log info message with automatic base64 sanitization."""
    logger = get_logger(logger_name)
    if data:
        sanitized_data = sanitize_base64_data(data)
        logger.info(f"{message}: {safe_json_dumps(sanitized_data)}")
    else:
        logger.info(message)


def safe_debug(message: str, data: Optional[Dict[str, Any]] = None, logger_name: str = 'disparaai') -> None:
    """Log debug message with automatic base64 sanitization."""
    logger = get_logger(logger_name)
    if data:
        sanitized_data = sanitize_base64_data(data)
        logger.debug(f"{message}: {safe_json_dumps(sanitized_data)}")
    else:
        logger.debug(message)