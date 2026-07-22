from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .models import Vehicle, vehicle_device_info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AitoDataCoordinator = data["coordinator"]
    vehicles: list[Vehicle] = data["vehicles"]
    async_add_entities(AitoDeviceTracker(coordinator, vehicle) for vehicle in vehicles)


class AitoDeviceTracker(CoordinatorEntity[AitoDataCoordinator], TrackerEntity):
    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle) -> None:
        super().__init__(coordinator)
        self.vehicle = vehicle
        self._attr_has_entity_name = True
        self._attr_name = "Location"
        self._attr_unique_id = f"{vehicle.id}_location"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def latitude(self) -> float | None:
        location = self._location()
        value = location["latitude"] if "latitude" in location else location.get("lat")
        return _coordinate(value, minimum=-90, maximum=90)

    @property
    def longitude(self) -> float | None:
        location = self._location()
        value = location["longitude"] if "longitude" in location else location.get("lon")
        return _coordinate(value, minimum=-180, maximum=180)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _location(self) -> dict:
        location = self.coordinator.data.get(self.vehicle.id, {}).get("location") or {}
        if not isinstance(location, dict):
            return {}
        nested = location.get("location") if isinstance(location, dict) else None
        return nested if isinstance(nested, dict) else location


def _coordinate(value, *, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if coordinate < minimum or coordinate > maximum:
        return None
    return coordinate
