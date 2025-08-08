"""Translation helper for Trafiklab integration."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

_LOGGER = logging.getLogger(__name__)

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
DEFAULT_LANGUAGE = "en"


class TranslationHelper:
    """Helper class for accessing translations."""

    def __init__(self, hass: HomeAssistant | None = None, language: str = DEFAULT_LANGUAGE) -> None:
        """Initialize translation helper."""
        self.hass = hass
        self.language = language
        self._translations: dict[str, Any] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load translations from files."""
        try:
            translation_file = TRANSLATIONS_DIR / f"{self.language}.json"
            if not translation_file.exists() and self.language != DEFAULT_LANGUAGE:
                # Fallback to English if requested language doesn't exist
                translation_file = TRANSLATIONS_DIR / f"{DEFAULT_LANGUAGE}.json"
            
            if translation_file.exists():
                with open(translation_file, encoding="utf-8") as f:
                    self._translations = json.load(f)
            else:
                _LOGGER.warning("No translation file found for language %s", self.language)
        except Exception as err:
            _LOGGER.error("Error loading translations: %s", err)

    def get(self, key: str, **kwargs) -> str:
        """Get translated string by key with optional formatting."""
        keys = key.split(".")
        value = self._translations
        
        try:
            for k in keys:
                value = value[k]
            
            # If value is a string, format it if kwargs are provided
            if isinstance(value, str) and kwargs:
                return value.format(**kwargs)
            return str(value)
        except (KeyError, TypeError):
            _LOGGER.warning("Translation key not found: %s", key)
            return key

    def get_sensor_name(self, sensor_key: str) -> str:
        """Get sensor name translation."""
        return self.get(f"common.sensor_names.{sensor_key}")

    def get_state(self, state_key: str, **kwargs) -> str:
        """Get state translation."""
        return self.get(f"common.states.{state_key}", **kwargs)

    def get_device_info(self, info_key: str) -> str:
        """Get device info translation."""
        return self.get(f"common.device.{info_key}")

    def get_api_error(self, error_key: str, **kwargs) -> str:
        """Get API error translation."""
        return self.get(f"common.api_errors.{error_key}", **kwargs)


# Global helper instance (will be initialized in __init__.py)
_translation_helper: TranslationHelper | None = None


def get_translation_helper() -> TranslationHelper:
    """Get the global translation helper instance."""
    global _translation_helper
    if _translation_helper is None:
        _translation_helper = TranslationHelper()
    return _translation_helper


def set_translation_helper(helper: TranslationHelper) -> None:
    """Set the global translation helper instance."""
    global _translation_helper
    _translation_helper = helper


def translate(key: str, **kwargs) -> str:
    """Convenience function to get translation."""
    return get_translation_helper().get(key, **kwargs)


def translate_sensor_name(sensor_key: str) -> str:
    """Convenience function to get sensor name translation."""
    return get_translation_helper().get_sensor_name(sensor_key)


def translate_state(state_key: str, **kwargs) -> str:
    """Convenience function to get state translation."""
    return get_translation_helper().get_state(state_key, **kwargs)


def translate_device_info(info_key: str) -> str:
    """Convenience function to get device info translation."""
    return get_translation_helper().get_device_info(info_key)


def translate_api_error(error_key: str, **kwargs) -> str:
    """Convenience function to get API error translation."""
    return get_translation_helper().get_api_error(error_key, **kwargs)
