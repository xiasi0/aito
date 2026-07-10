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
        return location["latitude"] if "latitude" in location else location.get("lat")

    @property
    def longitude(self) -> float | None:
        location = self._location()
        return location["longitude"] if "longitude" in location else location.get("lon")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _location(self) -> dict:
        location = self.coordinator.data.get(self.vehicle.id, {}).get("location") or {}
        nested = location.get("location") if isinstance(location, dict) else None
        return nested if isinstance(nested, dict) else location
