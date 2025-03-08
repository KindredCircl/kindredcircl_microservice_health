import os
import pytest
import yaml
from pydantic import ValidationError
from config.config import Config, CONFIG_ERRORS


# ✅ Centralized test data
VALID_CONFIG = {
    "logging": {
        "log_level": "INFO",
        "file_log_level": "DEBUG",
        "console_log_level": "WARNING",
        "log_file_path": "logs/app.log",
        "error_log_file_path": "logs/error.log",
        "log_queue_size": 10000,
        "max_log_file_size": 5000000,
        "max_backup_files": 5,
        "enable_memory_logging": True,
        "enable_execution_time_logging": True,
        "enable_request_metadata": True,
        "enable_stack_trace_logging": True,
    },
    "health": {
        "retry_count": 3,
        "timeout": 5,
        "enable_database_check": True,
        "enable_cache_check": True,
        "enable_messaging_check": True,
    },
    "database": {"url": "https://localhost:5432/health_db"},
    "cache": {"host": "cache.example.com", "port": 6379},
    "messaging": {"host": "messaging.example.com", "port": 5672},
    "alerts": {"slack_webhook": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX", "failure_threshold": 3},
}

INVALID_CONFIGS = {
    "missing_logging": {
        "error_match": "logging\n  Field required",
        "config": {k: v for k, v in VALID_CONFIG.items() if k != "logging"},
    },
    "invalid_log_level": {
        "error_match": "String should match pattern",
        "config": {**VALID_CONFIG, "logging": {**VALID_CONFIG["logging"], "log_level": "INVALID"}},
    },
    "invalid_port": {
        "error_match": "should be less than or equal to 65535",
        "config": {**VALID_CONFIG, "cache": {"host": "cache.example.com", "port": 999999}},
    },
    "invalid_url": {
        "error_match": "valid URL",
        "config": {**VALID_CONFIG, "database": {"url": "not_a_valid_url"}},
    },
    "negative_values": {
        "error_match": "should be greater than or equal to 1",
        "config": {**VALID_CONFIG, "health": {**VALID_CONFIG["health"], "retry_count": -1}},
    },
    "invalid_hostname": {
        "error_match": "String should have at least 3 characters",
        "config": {**VALID_CONFIG, "cache": {"host": "x", "port": 6379}},
    },
}

@pytest.fixture(autouse=True)
def clear_config_errors():
    """Ensures CONFIG_ERRORS is cleared before each test."""
    CONFIG_ERRORS.clear()

@pytest.fixture
def mock_config_file(tmp_path, request):
    """Creates a temporary YAML file with the requested config data."""
    config_file = tmp_path / "settings.yaml"
    with open(config_file, "w") as f:
        yaml.dump(request.param, f)
    return str(config_file)

@pytest.mark.parametrize("mock_config_file", [VALID_CONFIG], indirect=True)
def test_load_valid_config(mock_config_file):
    """✅ Test that valid configurations load correctly."""
    config = Config.load(mock_config_file)
    assert config.logging.log_level == "INFO"
    assert str(config.database.url) == "https://localhost:5432/health_db"

@pytest.mark.parametrize("invalid_case", INVALID_CONFIGS.keys())
def test_invalid_configs(invalid_case, tmp_path):
    """❌ Test multiple invalid configurations with specific error matching."""
    config_file = tmp_path / "settings.yaml"
    with open(config_file, "w") as f:
        yaml.dump(INVALID_CONFIGS[invalid_case]["config"], f)

    with pytest.raises(ValidationError, match=INVALID_CONFIGS[invalid_case]["error_match"]):
        Config.load(str(config_file))

@pytest.mark.parametrize("mock_config_file", [VALID_CONFIG], indirect=True)
def test_env_variable_override(monkeypatch, mock_config_file):
    """✅ Test valid environment variable overrides."""
    monkeypatch.setenv("HEALTH_DB_URL", "https://override.example.com")
    config = Config.load(mock_config_file)
    assert str(config.database.url) == "https://override.example.com/"

@pytest.mark.parametrize("mock_config_file", [VALID_CONFIG], indirect=True)
def test_env_variable_empty_value(monkeypatch, mock_config_file):
    """✅ Test that an empty environment variable falls back to YAML value."""
    monkeypatch.setenv("HEALTH_DB_URL", "")
    config = Config.load(mock_config_file)
    assert str(config.database.url) == "https://localhost:5432/health_db"

def test_invalid_yaml(tmp_path):
    """❌ Test that an invalid YAML file raises a `yaml.YAMLError`."""
    config_file = tmp_path / "invalid_settings.yaml"
    config_file.write_text("invalid_yaml: : : :\n")

    with pytest.raises(yaml.YAMLError, match="Error parsing YAML file"):
        Config.load(str(config_file))

@pytest.mark.parametrize("mock_config_file", [VALID_CONFIG], indirect=True)
def test_env_variable_invalid_port(monkeypatch, mock_config_file):
    """❌ Test that an invalid environment variable port raises a validation error."""
    monkeypatch.setenv("HEALTH_CACHE_PORT", "999999")
    with pytest.raises(ValidationError, match="should be less than or equal to 65535"):
        Config.load(mock_config_file)

@pytest.mark.parametrize("mock_config_file", [VALID_CONFIG], indirect=True)
def test_env_variable_extra_spaces(monkeypatch, mock_config_file):
    """✅ Test that environment variable with extra spaces is trimmed correctly."""
    monkeypatch.setenv("HEALTH_DB_URL", "  https://trimmed-url.com  ")
    config = Config.load(mock_config_file)
    assert str(config.database.url) == "https://trimmed-url.com/"

@pytest.mark.parametrize("mock_config_file", [VALID_CONFIG], indirect=True)
def test_env_variable_non_string(monkeypatch, mock_config_file):
    """✅ Test that a numeric environment variable is converted to an integer where required."""
    monkeypatch.setenv("HEALTH_CACHE_PORT", "6380")
    config = Config.load(mock_config_file)
    assert config.cache.port == 6380

def test_missing_config_file():
    """❌ Test that a missing configuration file raises an error."""
    with pytest.raises(FileNotFoundError):
        Config.load("non_existent.yaml")

def test_config_errors_storage():
    """✅ Ensure that config errors are captured in CONFIG_ERRORS."""
    with pytest.raises(FileNotFoundError):
        Config.load("non_existent.yaml")
    assert len(CONFIG_ERRORS) > 0

def test_empty_settings_file(tmp_path):
    """❌ Test that an empty settings file raises a `ValueError`."""
    config_file = tmp_path / "empty_settings.yaml"
    config_file.write_text("")  # ✅ Write an empty file
    with pytest.raises(ValueError, match="Configuration file is empty or invalid."):
        Config.load(str(config_file))

def test_generate_json_schema():
    """✅ Test that JSON schema is generated correctly."""
    schema = Config.generate_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "database" in schema["properties"]
    assert "logging" in schema["properties"]
