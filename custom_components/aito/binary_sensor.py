from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .models import Vehicle, vehicle_device_info
from .status_fields import BINARY_SENSOR_FIELDS, StatusField


@dataclass(frozen=True, kw_only=True)
class AitoBinarySensorDescription(BinarySensorEntityDescription):
    value_key: str


DEVICE_CLASS_MAP = {
    "battery": "BATTERY",
    "connectivity": "CONNECTIVITY",
    "door": "DOOR",
    "light": "LIGHT",
    "moving": "MOVING",
    "opening": "OPENING",
    "problem": "PROBLEM",
    "window": "WINDOW",
}


def _binary_sensor_description(field: StatusField) -> AitoBinarySensorDescription:
    return AitoBinarySensorDescription(
        key=field.key,
        translation_key=field.key,
        value_key=field.key,
        device_class=_binary_sensor_device_class(field.device_class),
    )


def _binary_sensor_device_class(device_class: str | None) -> Any:
    if device_class is None:
        return None
    return getattr(BinarySensorDeviceClass, DEVICE_CLASS_MAP.get(device_class, device_class.upper()), device_class)


BINARY_SENSORS = tuple(_binary_sensor_description(field) for field in BINARY_SENSOR_FIELDS)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AitoDataCoordinator = data["coordinator"]
    vehicles: list[Vehicle] = data["vehicles"]
    entities = [AitoDataAvailableSensor(coordinator, vehicle) for vehicle in vehicles]
    entities.extend(
        AitoBinarySensor(coordinator, vehicle, description) for vehicle in vehicles for description in BINARY_SENSORS
    )
    async_add_entities(entities)


class AitoDataAvailableSensor(CoordinatorEntity[AitoDataCoordinator], BinarySensorEntity):
    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle) -> None:
        super().__init__(coordinator)
        self.vehicle = vehicle
        self._attr_has_entity_name = True
        self._attr_translation_key = "data_available"
        self._attr_unique_id = f"{vehicle.id}_online"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def is_on(self) -> bool:
        return self.vehicle.id in self.coordinator.data


class AitoBinarySensor(CoordinatorEntity[AitoDataCoordinator], BinarySensorEntity):
    entity_description: AitoBinarySensorDescription

    def __init__(
        self,
        coordinator: AitoDataCoordinator,
        vehicle: Vehicle,
        description: AitoBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.vehicle = vehicle
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{vehicle.id}_{description.key}"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(self.vehicle.id, {}).get(self.entity_description.value_key)
        return value if isinstance(value, bool) else None
