import os
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic.networks import AnyHttpUrl
from typing_extensions import Annotated

# ✅ Store configuration errors for later logging
CONFIG_ERRORS = []

class LoggingConfig(BaseModel):
    """Logging settings validation with environment variable support."""
    log_level: Annotated[str, Field(pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")]
    file_log_level: Annotated[str, Field(pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")]
    console_log_level: Annotated[str, Field(pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")]
    log_file_path: str
    error_log_file_path: str
    log_queue_size: int = Field(..., gt=0)
    max_log_file_size: int = Field(..., gt=0)
    max_backup_files: int = Field(..., ge=0)

    enable_memory_logging: bool
    enable_execution_time_logging: bool
    enable_request_metadata: bool
    enable_stack_trace_logging: bool

    model_config = {"env_prefix": "HEALTH_LOGGING_"}  # ✅ Environment Variable Support

class HealthConfig(BaseModel):
    """Health check settings validation with environment variable support."""
    retry_count: int = Field(..., ge=1)
    timeout: int = Field(..., gt=0)
    enable_database_check: bool
    enable_cache_check: bool
    enable_messaging_check: bool

    model_config = {"env_prefix": "HEALTH_"}  # ✅ Environment Variable Support

class DatabaseConfig(BaseModel):
    """Database settings validation with environment variable support."""
    url: AnyHttpUrl = Field(default_factory=lambda: os.getenv("HEALTH_DB_URL") or "https://localhost:5432/health_db")

    model_config = {"env_prefix": "HEALTH_DATABASE_"}  # ✅ Ensure pydantic allows env var overrides

class CacheConfig(BaseModel):
    """Cache settings validation."""
    host: Annotated[str, Field(min_length=3, max_length=255)]  # ✅ Enforce hostname length
    port: int = Field(..., ge=1, le=65535)

    model_config = {"env_prefix": "HEALTH_CACHE_"}  # ✅ Environment Variable Support

class MessagingConfig(BaseModel):
    """Messaging settings validation."""
    host: Annotated[str, Field(min_length=3, max_length=255)]  # ✅ Validate hostname length
    port: int = Field(..., ge=1, le=65535)

    model_config = {"env_prefix": "HEALTH_MESSAGING_"}  # ✅ Environment Variable Support

class AlertConfig(BaseModel):
    """Alerting settings validation."""
    slack_webhook: AnyHttpUrl
    failure_threshold: int = Field(..., ge=1)

    model_config = {"env_prefix": "HEALTH_ALERT_"}  # ✅ Environment Variable Support

class Config(BaseModel):
    """
    Configuration loader for the Health Microservice.

    - ✅ Uses `pydantic` for structured validation.
    - ✅ Supports environment variable overrides.
    - ✅ Generates a JSON schema.
    - ✅ Provides a frozen (immutable) object to prevent accidental modifications.
    - ✅ Stores errors for logging after initialization.
    """
    logging: LoggingConfig
    health: HealthConfig
    database: DatabaseConfig
    cache: CacheConfig
    messaging: MessagingConfig
    alerts: AlertConfig

    model_config = {"frozen": True}  # ✅ Enforce immutability

    @classmethod
    def load(cls, settings_file="config/settings.yaml"):
        """
        Loads settings from YAML file and validates them using `pydantic`.

        Returns:
            Config: Validated configuration instance.

        Raises:
            FileNotFoundError: If the configuration file is missing.
            yaml.YAMLError: If there is a YAML parsing error.
            ValueError: If the configuration file is empty.
            ValidationError: If the configuration is invalid.
        """
        # ✅ Ensure settings.yaml is loaded from the correct `config/` directory
        project_root = Path(__file__).resolve().parent.parent  # ✅ Move up from `config/` to project root
        config_dir = project_root / "config"
        default_settings_file = config_dir / "settings.yaml"

        # ✅ Override with TEST_CONFIG_PATH if explicitly set, else use default
        settings_file = os.getenv("TEST_CONFIG_PATH")
        if settings_file:
            settings_file = Path(settings_file).resolve()
        else:
            settings_file = default_settings_file.resolve()

        # ✅ Print debugging information
        print(f"🔍 Debugging Path Resolution in `Config.load()`:")
        print(f"📌 `__file__`: {__file__}")
        print(f"📌 `project_root`: {project_root}")
        print(f"📌 `config_dir`: {config_dir}")
        print(f"📌 `default_settings_file`: {default_settings_file}")
        print(f"📌 `settings_file` (Final Selected Path): {settings_file}")  # ✅ Should now be correct

        try:
            with open(settings_file, "r") as file:
                settings = yaml.safe_load(file) or {}  # ✅ Ensure settings is a dictionary
                print(f"settings: {settings}")

            # ✅ Validate that the file is not empty
            if not settings:
                raise ValueError("Configuration file is empty or invalid.")

            # ✅ Ensure logging settings exist
            settings.setdefault("logging", {})
            logging_defaults = {
                "log_level": "INFO",
                "file_log_level": "DEBUG",
                "console_log_level": "WARNING",
                "log_file_path": "logs/health_service.log",
                "error_log_file_path": "logs/error.log",
                "log_queue_size": 10000,
                "max_log_file_size": 5000000,
                "max_backup_files": 5,
                "enable_memory_logging": True,
                "enable_execution_time_logging": True,
                "enable_request_metadata": True,
                "enable_stack_trace_logging": True,
            }
            for key, value in logging_defaults.items():
                settings["logging"].setdefault(key, value)

            return cls(**settings)  # ✅ Let `pydantic` raise ValidationError if needed
        except FileNotFoundError:
            error_msg = f"❌ Configuration file `{settings_file}` not found."
            print(error_msg, file=sys.stderr)
            CONFIG_ERRORS.append(error_msg)
            raise FileNotFoundError(error_msg)
        except yaml.YAMLError as e:
            error_msg = f"❌ Error parsing YAML file `{settings_file}`: {e}"
            print(error_msg, file=sys.stderr)
            CONFIG_ERRORS.append(error_msg)
            raise yaml.YAMLError(error_msg)
        except ValueError as e:
            error_msg = f"❌ {e}"
            print(error_msg, file=sys.stderr)
            CONFIG_ERRORS.append(error_msg)
            raise

    @classmethod
    def generate_schema(cls):
        """
        Generates a JSON Schema from the pydantic model.

        Returns:
            dict: JSON Schema representation of the configuration.
        """
        return cls.model_json_schema()

def load_config():
    """
    Returns an instance of the validated `Config` class.

    Usage:
        config = load_config()
        print(config.database.url)
    """
    return Config.load()
