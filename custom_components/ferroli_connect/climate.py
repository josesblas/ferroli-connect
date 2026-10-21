"""Climate (thermostat) platform for Ferroli Connect."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FerroliRuntime
from .const import DOMAIN, SIGNAL_UPDATE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: FerroliRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FerroliClimate(runtime)])


class FerroliClimate(ClimateEntity):
    """Thermostat backed by the Ferroli receiver."""

    _attr_has_entity_name = True
    _attr_translation_key = "thermostat"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 0
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, runtime: FerroliRuntime) -> None:
        self._rt = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_thermostat"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.cid)},
            name="Caldera Ferroli",
            manufacturer="Ferroli",
            model="Ferroli Connect",
        )

    @property
    def current_temperature(self) -> float | None:
        return self._rt.state.get("room_temp")

    @property
    def target_temperature(self) -> float | None:
        return self._rt.state.get("setpoint")

    @property
    def hvac_action(self) -> HVACAction | None:
        """Lo que hace el termostato *ahora* (calentando/inactivo).

        Prioriza la demanda (consigna > temperatura actual), como el termostato
        genérico de HA: si pides calor, muestra "calentando" aunque el quemador
        esté ciclando. El estado real del quemador se ve en el sensor
        `Estado caldera`.
        """
        target = self._rt.state.get("setpoint")
        current = self._rt.state.get("room_temp")
        if target is not None and current is not None and target > current:
            return HVACAction.HEATING
        # sin demanda por consigna: refleja el quemador si lo reporta encendido
        if self._rt.state.get("boiler_state") == "heating":
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._rt.async_set_setpoint(float(temp))

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(self._rt.entry.entry_id),
                self.async_write_ha_state,
            )
        )
