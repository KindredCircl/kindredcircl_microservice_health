import functools
import os
import random
import time

import psutil

LOG_SAMPLING_RATE = float(os.getenv("LOG_SAMPLING_RATE", 0.1))  # ✅ Default: 10%


def should_sample_log():
    """
    Determines whether a log should be sampled based on the configured sampling rate.

    Returns:
        bool: True if the log should be recorded, False otherwise.
    """
    return random.random() < LOG_SAMPLING_RATE


def get_memory_usage():
    """
    Returns the current process's memory usage in MB.

    Returns:
        float: Memory usage in megabytes (rounded to 2 decimal places), or "UNKNOWN" if retrieval fails.
    """
    try:
        process = psutil.Process()
        memory_usage_mb = process.memory_info().rss / (1024 * 1024)  # Convert bytes to MB
        return round(memory_usage_mb, 2)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "UNKNOWN"  # ✅ Prevents logging failures due to permission or process errors


def track_execution_time(func):
    """
    Decorator that measures the execution time of a function and adds it to the logging metadata.

    Usage:
        @track_execution_time
        def some_function():
            ...
            return result

    The execution time is stored in `log_extra["execution_time_ms"]` for logging purposes.

    Returns:
        Function result (unchanged), while execution time is stored in `log_extra`.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time_ms = round((time.time() - start_time) * 1000, 2)  # Convert to ms

        # ✅ Store execution time in logging metadata
        if "log_extra" in kwargs:
            kwargs["log_extra"]["execution_time_ms"] = execution_time_ms
        return result

    return wrapper


class ExecutionTimer:
    """
    Context manager for measuring execution time within a code block.

    Usage:
        with ExecutionTimer() as timer:
            some_code()
        print(timer.execution_time_ms)  # Access execution time after the block ends.

    Attributes:
        execution_time_ms (float): The execution time of the block in milliseconds.
    """

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.execution_time_ms = round((time.time() - self.start_time) * 1000, 2)  # Convert to ms
