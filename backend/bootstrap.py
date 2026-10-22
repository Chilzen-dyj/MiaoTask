"""Composition entry points shared by CLI and developer integrations."""
from backend.core.registry import create_runner, default_registry
from backend.core.config.loader import load_config
from backend.core.config.schema import validate_config
