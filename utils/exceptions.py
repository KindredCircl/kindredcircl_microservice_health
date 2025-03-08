# Base Exception for KindredCircl Microservice
class KindredCirclError(Exception):
    """Base class for all KindredCircl microservice exceptions."""
    pass

# Configuration Exceptions
class ConfigurationError(KindredCirclError):
    """Raised when there is an error in the configuration."""
    pass

class LoggingConfigurationError(ConfigurationError):
    """Raised when there is an error in the logging configuration."""
    pass
