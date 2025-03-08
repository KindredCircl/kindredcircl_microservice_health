import inspect
import os
import logging
import queue
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from utils.custom_json_formatter import CustomJSONFormatter
from utils.logging_helpers import get_memory_usage
from config.config import Config, CONFIG_ERRORS

class LoggingConfigurationError(Exception):
    """Custom exception for logging configuration errors."""
    pass

class SafeQueueListener(QueueListener):
    """
    Custom QueueListener that wraps handler execution with error handling.
    This prevents silent logging failures if a handler throws an exception.
    """

    def handle(self, record):
        """
        Process log records from the queue with error handling.
        """
        try:
            super().handle(record)
        except Exception as e:
            print(f"❌ Logging error while processing queue record: {e}")  # Last-resort fallback to stderr

def configure_logging(config: Config):
    """
    Configures structured JSON logging with:
    - ✅ Asynchronous logging via QueueHandler for performance.
    - ✅ RotatingFileHandler with customizable rotation settings.
    - ✅ Separate log levels for file and console.
    - ✅ SafeQueueListener to prevent silent logging failures.
    - ✅ Configurable log file location and security measures.
    - ✅ Compatibility with `CustomJSONFormatter` to preserve request metadata, tracing, system info, execution time, memory usage, and stack traces.

    Args:
        config (Config): Injected configuration instance.

    Returns:
        logging.Logger: Configured logger instance.
    """
    try:
        log_level = config.logging.log_level
        file_log_level = config.logging.file_log_level
        console_log_level = config.logging.console_log_level

        log_file = config.logging.log_file_path
        error_log_file = config.logging.error_log_file_path

        max_queue_size = config.logging.log_queue_size
        max_log_file_size = config.logging.max_log_file_size
        max_backup_files = config.logging.max_backup_files

        # ✅ Ensure log directories exist
        for path in [log_file, error_log_file]:
            log_dir = os.path.dirname(path)
            os.makedirs(log_dir, exist_ok=True)

        # ✅ Ensure log files exist before changing permissions
        for path in [log_file, error_log_file]:
            if not os.path.exists(path):
                open(path, "a").close()  # ✅ Create empty log file if it doesn't exist
            os.chmod(path, 0o600)  # ✅ Now safe to change permissions

        # ✅ Create structured JSON formatter
        formatter = CustomJSONFormatter()

        # ✅ Set up async logging queue
        log_queue = queue.Queue(max_queue_size)
        queue_handler = QueueHandler(log_queue)

        # ✅ File Handler (Rotating logs with configurable settings)
        file_handler = RotatingFileHandler(log_file, maxBytes=max_log_file_size, backupCount=max_backup_files)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(file_log_level)

        # ✅ Error Log Handler (for internal logging failures)
        error_handler = RotatingFileHandler(error_log_file, maxBytes=max_log_file_size, backupCount=max_backup_files)
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)

        # ✅ Stream Handler (Console logging)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(console_log_level)

        # ✅ Safe Queue Listener with error handling
        listener = SafeQueueListener(log_queue, file_handler, stream_handler, respect_handler_level=True)
        listener.start()  # ✅ Start logging thread

        # ✅ Configure root logger
        logger = logging.getLogger()
        if logger.hasHandlers():
            logger.handlers.clear()
        # ✅ Ensure StreamHandler is explicitly added
        logger.addHandler(stream_handler)  # 🔥 Add console logging (StreamHandler)
        logger.addHandler(file_handler)  # ✅ Ensure logs go directly to file as well
        logger.addHandler(queue_handler)  # ✅ Uses QueueHandler to route logs
        logger.setLevel(log_level)
        logger.propagate = False

        # ✅ Separate logger for logging errors
        error_logger = logging.getLogger("logging_errors")
        error_logger.addHandler(error_handler)
        error_logger.setLevel(logging.ERROR)

        # ✅ Capture and log configuration errors if they exist
        if CONFIG_ERRORS:
            for error in CONFIG_ERRORS:
                error_logger.error(f"⚠️ Configuration Error: {error}")

        # ✅ Capture memory usage if enabled
        if config.logging.enable_memory_logging:
            memory_usage_mb = get_memory_usage()
            logger.info("ℹ️ Logging system initialized", extra={"memory_usage_mb": memory_usage_mb})

        # ✅ Ensure stack traces are included when logging errors
        if config.logging.enable_stack_trace_logging:
            formatter.include_stack_trace = True  # Make sure CustomJSONFormatter is configured properly

        return logger

    except Exception as e:
        raise LoggingConfigurationError(f"❌ Error configuring logging: {e}")
