from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
try:
    from homeassistant.components.sensor import SensorStateClass
except ImportError:
    SensorStateClass = None
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .models import DYNAMIC_SENSOR_FIELDS, DynamicSensorField, Vehicle, vehicle_device_info


@dataclass(frozen=True, kw_only=True)
class AitoSensorDescription(SensorEntityDescription):
    value_key: str


UNIT_MAP = {
    "%": PERCENTAGE,
    "km": UnitOfLength.KILOMETERS,
    "\u00b0C": UnitOfTemperature.CELSIUS,
}

DEVICE_CLASS_MAP = {
    "battery": "BATTERY",
    "current": "CURRENT",
    "distance": "DISTANCE",
    "duration": "DURATION",
    "enum": "ENUM",
    "power": "POWER",
    "pressure": "PRESSURE",
    "speed": "SPEED",
    "temperature": "TEMPERATURE",
    "voltage": "VOLTAGE",
}


def _sensor_description(field: DynamicSensorField) -> AitoSensorDescription:
    return AitoSensorDescription(
        key=field.key,
        translation_key=field.key,
        value_key=field.key,
        native_unit_of_measurement=UNIT_MAP.get(field.unit, field.unit),
        device_class=_sensor_device_class(field.device_class),
        state_class=_sensor_state_class(field.state_class),
        options=list(field.options) if field.options else None,
    )


def _sensor_device_class(device_class: str | None) -> Any:
    if device_class is None:
        return None
    return getattr(SensorDeviceClass, DEVICE_CLASS_MAP.get(device_class, device_class.upper()), device_class)


def _sensor_state_class(state_class: str | None) -> Any:
    if state_class is None or SensorStateClass is None:
        return state_class
    return getattr(SensorStateClass, state_class.upper(), state_class)


SENSORS = tuple(_sensor_description(field) for field in DYNAMIC_SENSOR_FIELDS)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AitoDataCoordinator = data["coordinator"]
    vehicles: list[Vehicle] = data["vehicles"]
    async_add_entities(AitoSensor(coordinator, vehicle, description) for vehicle in vehicles for description in SENSORS)


class AitoSensor(CoordinatorEntity[AitoDataCoordinator], SensorEntity):
    entity_description: AitoSensorDescription

    def __init__(
        self,
        coordinator: AitoDataCoordinator,
        vehicle: Vehicle,
        description: AitoSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.vehicle = vehicle
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{vehicle.id}_{description.key}"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.vehicle.id, {}).get(self.entity_description.value_key)
