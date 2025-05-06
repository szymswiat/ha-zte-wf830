"""Platform for button integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZteNode, ZteWf830ApiClient
from .const import DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    api_client: ZteWf830ApiClient = hass.data[DOMAIN][entry.entry_id]

    device_serial_number = await hass.async_add_executor_job(
        api_client.get_serial_number
    )

    add_entities(
        [
            ZteResetButton(
                device_serial_number,
                "Reboot",
                api_client,
            )
        ]
    )


class ZteResetButton(ButtonEntity):
    """Representation of a Button."""

    def __init__(
        self,
        device_id: str,
        name: str,
        api_client: ZteWf830ApiClient,
    ) -> None:
        super().__init__()

        self._attr_name = f"{DEVICE_NAME} {device_id} {name}"
        self._attr_unique_id = f"{device_id}_{name}"

        self.api_client = api_client

        self.device_id = device_id

    @property
    def device_info(self) -> DeviceInfo | None:
        assert self.unique_id
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=DEVICE_NAME,
            default_manufacturer="ZTE",
            default_model="WF830",
        )

    @property
    def device_class(self) -> ButtonDeviceClass | None:
        return ButtonDeviceClass.RESTART

    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.api_client.reboot)

    @property
    def should_poll(self) -> bool:
        return True

    async def async_update_ha_state(self, force_refresh: bool = False) -> None:
        await self.hass.async_add_executor_job(
            self.api_client.get_node_value, [ZteNode.GET_SIGNAL_STRENGTH]
        )
