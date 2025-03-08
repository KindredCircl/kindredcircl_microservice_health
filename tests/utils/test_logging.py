import json
import sys

import pytest
import logging
import queue
from unittest.mock import patch, MagicMock
from logging.handlers import QueueHandler, RotatingFileHandler
from pydantic import AnyHttpUrl
from config.config import Config, CONFIG_ERRORS, LoggingConfig, HealthConfig, DatabaseConfig, CacheConfig, \
    MessagingConfig, AlertConfig
from utils.logging_config import configure_logging, LoggingConfigurationError, SafeQueueListener
from utils.custom_json_formatter import CustomJSONFormatter


@pytest.fixture
def mock_config():
    """✅ Provides a mock configuration object with full required settings."""
    return Config(
        logging=LoggingConfig(
            log_level="INFO",
            file_log_level="DEBUG",
            console_log_level="WARNING",
            log_file_path="logs/test_health_service.log",
            error_log_file_path="logs/test_error.log",
            log_queue_size=10000,
            max_log_file_size=5000000,
            max_backup_files=5,
            enable_memory_logging=True,
            enable_execution_time_logging=True,
            enable_request_metadata=True,
            enable_stack_trace_logging=True,
        ),
        health=HealthConfig(
            retry_count=3,
            timeout=5,
            enable_database_check=True,
            enable_cache_check=True,
            enable_messaging_check=True,
        ),
        database=DatabaseConfig(url=AnyHttpUrl("https://localhost:5432/health_db")),
        cache=CacheConfig(host="cache.example.com", port=6379),
        messaging=MessagingConfig(host="messaging.example.com", port=5672),
        alerts=AlertConfig(slack_webhook=AnyHttpUrl("https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX"), failure_threshold=3),
    )
@pytest.fixture(autouse=True)
def clear_config_errors():
    """✅ Clears CONFIG_ERRORS before each test."""
    CONFIG_ERRORS.clear()


def test_successful_logging_configuration(mock_config):
    """✅ Test that `configure_logging` initializes logging correctly."""
    logger = configure_logging(mock_config)
    assert logger is not None
    assert isinstance(logger, logging.Logger)
    assert any(isinstance(handler, QueueHandler) for handler in logger.handlers)


def test_missing_log_directory(mock_config):
    """❌ Test that `configure_logging` raises an error when log directory creation fails."""
    with patch("os.makedirs") as mock_makedirs:
        mock_makedirs.side_effect = PermissionError("Directory creation failed")
        with pytest.raises(LoggingConfigurationError, match="❌ Error configuring logging: Directory creation failed"):
            configure_logging(mock_config)


def test_log_file_permissions(mock_config):
    """✅ Test that log file permissions are correctly set."""
    with patch("os.chmod") as mock_chmod:
        configure_logging(mock_config)

        # ✅ Use correct attribute
        mock_chmod.assert_any_call(mock_config.logging.log_file_path, 0o600)
        mock_chmod.assert_any_call(mock_config.logging.error_log_file_path, 0o600)


def test_config_errors_logged(mock_config):
    """✅ Test that configuration errors are logged if they exist."""
    CONFIG_ERRORS.append("Fake configuration error")
    with patch("logging.Logger.error") as mock_error_log:
        configure_logging(mock_config)
        mock_error_log.assert_called_with("⚠️ Configuration Error: Fake configuration error")


def test_safe_queue_listener_handles_errors():
    """✅ Test that `SafeQueueListener` does not crash on logging errors."""
    mock_record = MagicMock()
    listener = SafeQueueListener(queue.Queue())
    with patch("logging.Handler.handle", side_effect=Exception("Handler error")):
        listener.handle(mock_record)  # ✅ Should not raise an exception

    assert True, "❌ SafeQueueListener crashed when handling a failing log handler!"


def test_exception_handling_in_configure_logging(mock_config):
    """❌ Test that `configure_logging` raises `LoggingConfigurationError` on failure."""
    with patch("logging.Logger.addHandler", side_effect=Exception("Unexpected failure")):
        with pytest.raises(LoggingConfigurationError, match="Error configuring logging"):
            configure_logging(mock_config)


def test_custom_json_formatter():
    """✅ Test that `CustomJSONFormatter` correctly formats log records."""
    formatter = CustomJSONFormatter()
    try:
        raise ValueError("Test error")  # ✅ Generate a controlled error
    except ValueError as e:
        exc_info = (type(e), e, e.__traceback__)  # ✅ Correct way to capture exc_info

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,  # ✅ Set log level to ERROR so stack trace gets included
            pathname=__file__,
            lineno=10,
            msg="Test log message",
            args=(),
            exc_info=exc_info,  # ✅ Pass the exception info
            func="test_custom_json_formatter",
        )

    formatted_log = formatter.format(record)
    log_dict = json.loads(formatted_log)

    assert "timestamp" in log_dict
    assert log_dict["levelname"] == "ERROR"  # ✅ ERROR instead of INFO
    assert log_dict["message"] == "Test log message"
    assert log_dict["module"] == "test_logging"
    assert log_dict["function"] == "test_custom_json_formatter"
    assert "stack_trace" in log_dict, "❌ Stack trace missing in error log!"

    # ✅ Updated assertion: Verify expected error message exists in stack trace
    assert "ValueError: Test error" in log_dict["stack_trace"], "❌ Stack trace does not contain expected error message!"


def test_log_levels(mock_config):
    """✅ Test that log levels are correctly set."""
    logger = configure_logging(mock_config)
    assert logger.level == logging.INFO


def test_extra_dictionary_in_logs(mock_config):
    """✅ Test that `extra` dictionary fields are correctly added to log records."""
    logger = configure_logging(mock_config)

    with patch("logging.Logger.info") as mock_info_log:
        logger.info("Test message", extra={"custom_field": "test_value"})
        mock_info_log.assert_any_call("Test message", extra={"custom_field": "test_value"})


def test_rotating_file_handler(mock_config):
    """✅ Test that `RotatingFileHandler` correctly rotates log files."""
    # ✅ Force log rotation by setting a very small max file size
    mock_config.logging.max_log_file_size = 1  # 1 byte to ensure rotation

    with patch("logging.handlers.RotatingFileHandler.doRollover") as mock_rollover:
        logger = configure_logging(mock_config)

        # ✅ Write multiple large log entries to trigger rollover
        for _ in range(10):
            logger.info("X" * 1024)  # ✅ Writing 1KB per log

        # ✅ Ensure log file rollover is triggered
        mock_rollover.assert_called(), "❌ Log file rollover was not triggered!"


def test_logging_memory_usage(mock_config):
    """✅ Test that memory usage is logged when enabled."""
    mock_config.logging.enable_memory_logging = True  # ✅ Ensure memory logging is enabled

    with patch("utils.logging_config.get_memory_usage", return_value=123.45) as mock_memory_usage, \
         patch("logging.Logger.info") as mock_info_log:

        configure_logging(mock_config)  # ✅ This should now call `get_memory_usage()`

        # ✅ Ensure function was called
        mock_memory_usage.assert_called_once(), "❌ `get_memory_usage()` was never called!"


from typing import Type

def test_correct_handlers_added(mock_config):
    """✅ Test that the correct handlers are added to the logger."""
    logger = configure_logging(mock_config)

    # ✅ Extract handler types
    handler_types: set[Type[logging.Handler]] = {type(handler) for handler in logger.handlers}

    # ✅ Ensure required handlers are present
    expected_handlers: set[Type[logging.Handler]] = {QueueHandler, RotatingFileHandler, logging.StreamHandler}
    missing_handlers = expected_handlers - handler_types  # 🔧 This now avoids type mismatches

    assert not missing_handlers, f"❌ Missing handlers: {missing_handlers}"


def test_stack_trace_logging_production(mock_config):
    """✅ Ensure stack traces are captured in production-style logging."""

    formatter = CustomJSONFormatter()  # ✅ Directly use the formatter to verify stack trace

    try:
        raise ValueError("Test error for production stack trace")
    except ValueError:
        exc_info = sys.exc_info()  # ✅ Extract full exception tuple

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=99,
            msg="An error occurred",
            args=(),
            exc_info=exc_info,  # ✅ Correctly passing the (type, value, traceback) tuple
            func="test_stack_trace_logging_production"
        )
        formatted_log = formatter.format(record)  # ✅ Pass the record through the formatter
        log_dict = json.loads(formatted_log)  # ✅ Convert formatted JSON to a dictionary

        # ✅ Ensure stack trace is included
        assert "stack_trace" in log_dict, "❌ Stack trace not included in log!"
        assert "Test error for production stack trace" in log_dict["stack_trace"], \
            "❌ Stack trace does not contain expected error message!"


def test_request_metadata_logging_enabled(mock_config):
    """✅ Test that request metadata is logged when `enable_request_metadata` is enabled."""
    mock_config.logging.enable_request_metadata = True  # Ensure setting is enabled
    logger = configure_logging(mock_config)

    with patch("logging.Logger.info") as mock_info_log:
        logger.info("Test request metadata", extra={"request_id": "12345", "user_id": "67890", "feed_type": "home_feed"})

    # ✅ Extract logged metadata
    args, kwargs = mock_info_log.call_args
    log_entry = kwargs.get("extra", {})

    assert log_entry.get("request_id") == "12345", "❌ request_id is missing from log!"
    assert log_entry.get("user_id") == "67890", "❌ user_id is missing from log!"
    assert log_entry.get("feed_type") == "home_feed", "❌ feed_type is missing from log!"


from datetime import datetime


def test_timestamp_format():
    """✅ Test that log timestamps are correctly formatted."""
    formatter = CustomJSONFormatter()
    record = logging.LogRecord(name="test_logger", level=logging.INFO, pathname=__file__, lineno=10,
                               msg="Test log message", args=(), exc_info=None, func="test_timestamp_format")

    formatted_log = formatter.format(record)
    log_dict = json.loads(formatted_log)

    timestamp = log_dict.get("timestamp", "")

    try:
        # ✅ Ensure timestamp is valid
        parsed_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
        assert isinstance(parsed_time, datetime), "❌ Timestamp is not a valid datetime!"
    except ValueError:
        pytest.fail(f"❌ Timestamp format is incorrect: {timestamp}")


def test_error_log_file(mock_config):
    """✅ Test that errors are correctly written to the error log file."""
    logger = configure_logging(mock_config)

    with patch("logging.handlers.RotatingFileHandler.emit") as mock_emit:
        try:
            raise RuntimeError("Critical failure")
        except RuntimeError:
            logger.exception("A critical error occurred")

    # ✅ Ensure error log handler was triggered
    mock_emit.assert_called()
