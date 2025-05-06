"""Platform for switch integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

# pylint: disable=no-name-in-module
from pydantic import BaseModel

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import LteBand, ZteWf830ApiClient
from .const import DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    api_client: ZteWf830ApiClient = hass.data[DOMAIN][entry.entry_id]

    coordinator = ZteSwitchUpdateCoordinator(hass, api_client, SCAN_INTERVAL)

    await coordinator.async_config_entry_first_refresh()

    device_serial_number = await hass.async_add_executor_job(
        api_client.get_serial_number
    )

    add_entities(
        [
            ZteBandSwitch(
                device_serial_number,
                band,
                coordinator,
            )
            for band in LteBand
        ]
    )


class ZteSwitchUpdateCoordinatorData(BaseModel):
    active_bands: list[LteBand]


class ZteSwitchUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        api_client: ZteWf830ApiClient,
        update_interval: timedelta,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="ZTE WF830",
            update_interval=update_interval,
        )

        self.api_client = api_client

    async def _async_update_data(self) -> ZteSwitchUpdateCoordinatorData:
        try:
            active_bands = await self.hass.async_add_executor_job(
                self.api_client.get_active_bands
            )

        except Exception as err:
            raise UpdateFailed(
                f"Communication with API failed: {type(err)}, {err}"
            ) from err

        return ZteSwitchUpdateCoordinatorData(
            active_bands=active_bands,
        )


class ZteBandSwitch(CoordinatorEntity[ZteSwitchUpdateCoordinator], SwitchEntity):
    """Representation of a Switch."""

    def __init__(
        self,
        device_id: str,
        bound_band: LteBand,
        coordinator: ZteSwitchUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)

        self._attr_name = f"{DEVICE_NAME} {device_id} {bound_band.name}"
        self._attr_unique_id = f"{device_id}_{bound_band.name}"
        self.bound_band = bound_band

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

    @callback
    def _handle_coordinator_update(self) -> None:
        fetched_data: ZteSwitchUpdateCoordinatorData = self.coordinator.data

        if not fetched_data:
            return

        self._attr_is_on = self.bound_band in fetched_data.active_bands

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(
            self.coordinator.api_client.set_band, self.bound_band
        )

        await self.coordinator._async_update_data()
