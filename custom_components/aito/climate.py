from __future__ import annotations

from math import isclose
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .models import Vehicle, vehicle_device_info

_PRESET_RAPID_COOL = "rapid_cool"
_PRESET_RAPID_HEAT = "rapid_heat"
_PRESET_DEFROST = "defrost"
_PRESETS = (_PRESET_RAPID_COOL, _PRESET_RAPID_HEAT, _PRESET_DEFROST)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.get("coordinator")
    if coordinator is None:
        return
    entities = [
        AitoAirConditioner(coordinator, vehicle)
        for vehicle in data["vehicles"]
        if (spec := data["vehicle_specs"].get(vehicle.id)) and spec.supports_air_conditioner
    ]
    async_add_entities(entities)


class AitoAirConditioner(CoordinatorEntity[AitoDataCoordinator], ClimateEntity):
    """Represent the vehicle's remotely controlled air conditioner."""

    _attr_has_entity_name = True
    _attr_translation_key = "air_conditioner"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
    _attr_preset_modes = list(_PRESETS)
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 31
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle.id
        self._attr_unique_id = f"{vehicle.id}_air_conditioner"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def available(self) -> bool:
        return super().available and self._hvac is not None

    @property
    def hvac_mode(self) -> HVACMode | None:
        status = self._value("acStatus")
        if status is None:
            return None
        return HVACMode.AUTO if status in {1, "1"} else HVACMode.OFF

    @property
    def target_temperature(self) -> float | None:
        return _target_temperature_celsius(self._value("remoteTemp"))

    @property
    def current_temperature(self) -> float | None:
        return _temperature_celsius(self._value("insideTemp"))

    @property
    def preset_mode(self) -> str | None:
        return self._active_preset

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        if hvac_mode == HVACMode.AUTO:
            await self.async_turn_on()
            return
        raise ValueError(f"unsupported AITO HVAC mode: {hvac_mode}")

    async def async_turn_on(self) -> None:
        target_temp = _target_temperature_tenths(self.target_temperature)
        await self.coordinator.async_control_air_conditioner(
            self._vehicle_id,
            enabled=True,
            target_temp=target_temp,
        )

    async def async_turn_off(self) -> None:
        await self.coordinator.async_control_air_conditioner(self._vehicle_id, enabled=False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        target_temp = _target_temperature_tenths(kwargs.get(ATTR_TEMPERATURE))
        await self.coordinator.async_control_air_conditioner(
            self._vehicle_id,
            enabled=True,
            target_temp=target_temp,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in _PRESETS:
            raise ValueError(f"unsupported AITO air-conditioner preset: {preset_mode}")
        active = self._active_preset
        if active == preset_mode:
            return
        if active is not None:
            await self._async_set_preset(active, enabled=False)
        await self._async_set_preset(preset_mode, enabled=True)

    async def _async_set_preset(self, preset: str, *, enabled: bool) -> None:
        if preset == _PRESET_RAPID_COOL:
            await self.coordinator.async_control_air_conditioner_rapid(
                self._vehicle_id,
                enabled=enabled,
                mode=1,
            )
            return
        if preset == _PRESET_RAPID_HEAT:
            await self.coordinator.async_control_air_conditioner_rapid(
                self._vehicle_id,
                enabled=enabled,
                mode=2,
            )
            return
        if preset == _PRESET_DEFROST:
            await self.coordinator.async_control_defrost(self._vehicle_id, enabled=enabled)

    @property
    def _active_preset(self) -> str | None:
        active = [
            preset
            for preset, field in (
                (_PRESET_RAPID_COOL, "maxColdSwitch"),
                (_PRESET_RAPID_HEAT, "maxHeatSwitch"),
                (_PRESET_DEFROST, "defrostStatus"),
            )
            if self._value(field) in {1, "1"}
        ]
        return active[0] if len(active) == 1 else None

    @property
    def _hvac(self) -> dict[str, Any] | None:
        data = self.coordinator.data.get(self._vehicle_id, {}) if self.coordinator.data else {}
        hvac = data.get("hvac")
        return hvac if isinstance(hvac, dict) else None

    def _value(self, field: str) -> Any:
        hvac = self._hvac
        return hvac.get(field) if hvac is not None else None


def _temperature_celsius(value: Any) -> float | None:
    return value / 10 if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _target_temperature_celsius(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not 160 <= value <= 310 or value % 5:
        return None
    return value / 10


def _target_temperature_tenths(value: Any) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("AITO air-conditioner temperature is required")
    if not 16 <= value <= 31 or not isclose(value * 2, round(value * 2)):
        raise ValueError("AITO air-conditioner temperature must be 16.0-31.0 C in 0.5 C steps")
    return round(value * 10)
