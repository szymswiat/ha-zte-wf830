"""The ZTE WF830 integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import ZteWf830ApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up ZTE WF830 from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api_client = ZteWf830ApiClient(
        host=entry.data["host"],
        smartadmin_password=entry.data["smartadmin_password"],
    )

    try:
        _LOGGER.info("Authenticating with ZTE WF830")
        hass.async_add_executor_job(api_client.authenticate)
    except Exception as err:
        raise ConfigEntryAuthFailed from err

    hass.data[DOMAIN][entry.entry_id] = api_client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
