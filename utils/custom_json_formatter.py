from datetime import datetime
import json
from types import TracebackType

import json_log_formatter
import socket
import time
import os
import traceback
from utils.logging_helpers import get_memory_usage
from config.config import load_config
import logging

config = load_config()



class CustomJSONFormatter(json_log_formatter.JSONFormatter):
    """
    Enhanced JSON formatter for structured logging.

    Features:
    - ✅ Preserves request metadata (`request_id`, `user_id`, `feed_type`).
    - ✅ Includes system debugging details (`module`, `function`, `line`, `process`, `thread`).
    - ✅ Adds traceability fields (`trace_id`, `span_id`) for distributed microservice logging.
    - ✅ Logs system context (`hostname`, `environment`).
    - ✅ Provides ISO 8601 timestamps with milliseconds for accurate log timing.
    - ✅ Captures execution time & memory usage if enabled in settings.
    - ✅ Includes stack trace for errors while ensuring safe error handling.
    - ✅ Configurable fields to enable/disable specific logging details.
    """

    def format(self, record):
        """
        Overrides `format()` to ensure `record` is passed correctly to `json_record`.
        """
        message = record.getMessage()
        extra = self._extract_extra_fields(record)  # ✅ Extract extra fields into a dictionary

        structured_record = self.json_record(log_record=record,message=message, extra=extra)

        # ✅ Add log level and timestamp
        structured_record["levelname"] = record.levelname
        structured_record["timestamp"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)
        ) + f".{int(record.msecs):03d}Z"

        # ✅ Ensure `time` is JSON serializable (Convert `datetime` to `str`)
        if isinstance(structured_record.get("time"), datetime):
            structured_record["time"] = structured_record["time"].isoformat()


        # ✅ Ensure structured debugging details are captured
        structured_record.update({
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
            "hostname": socket.gethostname(),
            "environment": os.getenv("ENVIRONMENT", "development"),
        })

        # ✅ Capture execution time if enabled
        if config.logging.enable_execution_time_logging:
            structured_record["execution_time_ms"] = getattr(record, "execution_time_ms", "UNKNOWN")

        # ✅ Capture memory usage if enabled
        if config.logging.enable_memory_logging:
            structured_record["memory_usage_mb"] = get_memory_usage()

        # ✅ Log stack trace safely
        if record.exc_info:
            structured_record["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(structured_record)

    def json_record(self, log_record, message, extra=None):
        """
        Formats a log record as structured JSON.

        Args:
            log_record (logging.LogRecord): The log record containing log details.
            message (str): The log message.
            extra (dict, optional): Additional metadata fields.

        Returns:
            dict: A structured log entry in JSON format.
        """
        if not isinstance(extra, dict):
            extra = {}

        record = super().json_record(message, extra, log_record)

        # ✅ Add request metadata if enabled
        if config.logging.enable_request_metadata:
            if isinstance(extra, dict): #Check if extra is a dict.
                record["request_id"] = getattr(log_record, "request_id", extra.get("request_id", "UNKNOWN"))
                record["user_id"] = getattr(log_record, "user_id", extra.get("user_id", "UNKNOWN"))
                record["feed_type"] = getattr(log_record, "feed_type", extra.get("feed_type", "UNKNOWN"))
            else:
                record["request_id"] = getattr(log_record, "request_id", "UNKNOWN")
                record["user_id"] = getattr(log_record, "user_id", "UNKNOWN")
                record["feed_type"] = getattr(log_record, "feed_type", "UNKNOWN")

        # ✅ Add traceability fields (used for distributed tracing in microservices)
        record["trace_id"] = getattr(log_record, "trace_id", getattr(extra, "trace_id", "UNKNOWN") if extra else "UNKNOWN")
        record["span_id"] = getattr(log_record, "span_id", getattr(extra, "span_id", "UNKNOWN") if extra else "UNKNOWN")

        # ✅ Include debugging details
        record["module"] = getattr(log_record, "module", "UNKNOWN")
        record["function"] = getattr(log_record, "funcName", "UNKNOWN")
        record["line"] = getattr(log_record, "lineno", "UNKNOWN")
        record["process"] = getattr(log_record, "process", "UNKNOWN")
        record["thread"] = getattr(log_record, "thread", "UNKNOWN")

        # ✅ Add system context
        record["hostname"] = socket.gethostname()
        record["environment"] = os.getenv("ENVIRONMENT", "development")

        # ✅ Use ISO 8601 format with milliseconds for precise timestamping
        record["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S",
                                            time.gmtime(log_record.created)) + f".{int(log_record.msecs):03d}Z"

        # ✅ Ensure all datetime objects are converted before serialization
        record["time"] = record["time"].isoformat() if isinstance(record.get("time"), datetime) else record.get("time")

        # ✅ Capture execution time if enabled
        if config.logging.enable_execution_time_logging:
            record["execution_time_ms"] = getattr(log_record, "execution_time_ms", "UNKNOWN")

        # ✅ Capture memory usage if enabled
        if config.logging.enable_memory_logging:
            record["memory_usage_mb"] = get_memory_usage()

        # ✅ Log stack trace safely
        try:
            # ✅ Print what's inside log_record before extracting exc_info

            if log_record.levelname in ["ERROR", "CRITICAL"] and log_record.exc_info is not None:
                exc_type, exc_value, exc_traceback = log_record.exc_info  # Unpack directly

                if isinstance(exc_traceback, TracebackType):  # ✅ Ensure traceback is valid
                    record["stack_trace"] = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                else:
                    record["stack_trace"] = "".join(traceback.format_exception(exc_type, exc_value))
            elif log_record.levelname in ["ERROR", "CRITICAL"] and log_record.exc_info is None:
                record["stack_trace"] = "⚠️ Exception occurred, but no exception info was available."

        except Exception as e:
            record["stack_trace"] = f"⚠️ Error retrieving stack trace: {str(e)}"
        return record

    def _extract_extra_fields(self, record):
        """
        Extracts additional log fields from the `record` object.

        Args:
            record (logging.LogRecord): The log record containing log details.

        Returns:
            dict: Extracted extra fields.
        """
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ["args", "msg", "exc_info", "exc_text", "created", "msecs", "relativeCreated", "stack_info"]:
                extra_fields[key] = value
        return extra_fields