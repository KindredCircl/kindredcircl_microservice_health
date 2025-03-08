from dependency_injector import containers, providers
from config.config import load_config
from utils.logging_config import configure_logging

class Container(containers.DeclarativeContainer):
    """
    Dependency Injection container for the Health Microservice.

    - ✅ Injects `Config` (from `config.py`) for centralized configuration management.
    - ✅ Injects `configure_logging()` (from `logging_config.py`) to ensure logging is initialized once.
    """

    # ✅ Load configuration
    config = providers.Singleton(load_config)

    # ✅ Initialize structured logging
    logging = providers.Singleton(configure_logging)
