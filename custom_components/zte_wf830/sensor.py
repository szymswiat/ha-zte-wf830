"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging

# pylint: disable=no-name-in-module
from pydantic import BaseModel

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import SignalParams, TransferStatus, ZteWf830ApiClient
from .const import DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    api_client: ZteWf830ApiClient = hass.data[DOMAIN][entry.entry_id]

    coordinator = ZteSensorUpdateCoordinator(hass, api_client, SCAN_INTERVAL)

    await coordinator.async_config_entry_first_refresh()

    device_serial_number = await hass.async_add_executor_job(
        api_client.get_serial_number
    )

    add_entities(
        [
            ZteSensor(
                device_serial_number,
                "Current Download",
                coordinator,
                lambda data: data.transfer_status.current_download // 1024,
                "KB/s",
            ),
            ZteSensor(
                device_serial_number,
                "Current Upload",
                coordinator,
                lambda data: data.transfer_status.current_upload // 1024,
                "KB/s",
            ),
            ZteSensor(
                device_serial_number,
                "Total Download",
                coordinator,
                lambda data: data.transfer_status.total_download // (1024 * 1024),
                "MB",
            ),
            ZteSensor(
                device_serial_number,
                "Total Upload",
                coordinator,
                lambda data: data.transfer_status.total_upload // (1024 * 1024),
                "MB",
            ),
            ZteSensor(
                device_serial_number,
                "Signal Strength",
                coordinator,
                lambda data: f"{data.signal_params.strength}/4",
                "",
            ),
            ZteSensor(
                device_serial_number,
                "WAN IP",
                coordinator,
                lambda data: data.signal_params.wan_ip_addr,
                "",
            ),
        ]
    )


class ZteSensorUpdateCoordinatorData(BaseModel):
    signal_params: SignalParams
    transfer_status: TransferStatus


class ZteSensorUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        api_client: ZteWf830ApiClient,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="ZTE WF830",
            update_interval=update_interval,
        )

        self.api_client = api_client

    async def _async_update_data(self) -> ZteSensorUpdateCoordinatorData:
        try:
            signal_params = await self.hass.async_add_executor_job(
                self.api_client.get_signal_params,
            )
            transfer_status = await self.hass.async_add_executor_job(
                self.api_client.get_transfer_status
            )

        except Exception as err:
            raise UpdateFailed(
                f"Communication with API failed: {type(err)}, {err}"
            ) from err

        return ZteSensorUpdateCoordinatorData(
            signal_params=signal_params,
            transfer_status=transfer_status,
        )


class ZteSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        device_id: str,
        name: str,
        coordinator: DataUpdateCoordinator,
        extract_state: Callable[[ZteSensorUpdateCoordinatorData], str | int],
        unit: str,
    ) -> None:
        super().__init__(coordinator)

        self._attr_name = f"{DEVICE_NAME} {device_id} {name}"
        self._attr_unique_id = f"{device_id}_{name.lower().replace(' ', '_')}"
        self._attr_native_unit_of_measurement = unit
        self.extract_state = extract_state

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
        fetched_data: ZteSensorUpdateCoordinatorData = self.coordinator.data

        if not fetched_data:
            return

        self._attr_native_value = self.extract_state(fetched_data)

        self.async_write_ha_state()
