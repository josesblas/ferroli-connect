"""Sensor platform for Ferroli Connect."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroliRuntime
from .const import DOMAIN, SIGNAL_UPDATE

_TEMP = dict(
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="room_temp", translation_key="room_temp", **_TEMP),
    SensorEntityDescription(key="setpoint", translation_key="setpoint", **_TEMP),
    SensorEntityDescription(key="flow_temp", translation_key="flow_temp", **_TEMP),
    SensorEntityDescription(key="dhw_temp", translation_key="dhw_temp", **_TEMP),
    SensorEntityDescription(
        key="dhw_flow",
        translation_key="dhw_flow",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key="boiler_state",
        translation_key="boiler_state",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "heating", "dhw", "on"],
        icon="mdi:fire",
    ),
    SensorEntityDescription(
        key="mode",
        translation_key="mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:tune",
    ),
    SensorEntityDescription(
        key="boiler_setpoint",
        translation_key="boiler_setpoint",
        entity_category=EntityCategory.DIAGNOSTIC,
        **_TEMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: FerroliRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(FerroliSensor(runtime, desc) for desc in SENSORS)


class FerroliSensor(SensorEntity):
    """A single decoded value from the receiver."""

    _attr_has_entity_name = True

    def __init__(
        self, runtime: FerroliRuntime, description: SensorEntityDescription
    ) -> None:
        self._rt = runtime
        self.entity_description = description
        self._attr_unique_id = f"{runtime.entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.cid)},
            name="Ferroli Connect",
            manufacturer="Ferroli",
            model="Ferroli Connect",
        )

    @property
    def native_value(self):
        return self._rt.state.get(self.entity_description.key)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(self._rt.entry.entry_id),
                self.async_write_ha_state,
            )
        )
