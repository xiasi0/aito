from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .models import Vehicle, vehicle_device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.get("coordinator")
    if coordinator is None:
        return
    async_add_entities(
        AitoVehicleLocationTracker(coordinator, vehicle)
        for vehicle in data["vehicles"]
        if (spec := data["vehicle_specs"].get(vehicle.id)) and spec.supports_location
    )


class AitoVehicleLocationTracker(CoordinatorEntity[AitoDataCoordinator], TrackerEntity):
    """Expose the vehicle's reported GPS location."""

    _attr_has_entity_name = True
    _attr_translation_key = "location"

    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle.id
        self._attr_unique_id = f"{vehicle.id}_location"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def available(self) -> bool:
        return super().available and self._coordinates is not None

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        coordinates = self._coordinates
        return coordinates[0] if coordinates is not None else None

    @property
    def longitude(self) -> float | None:
        coordinates = self._coordinates
        return coordinates[1] if coordinates is not None else None

    @property
    def _coordinates(self) -> tuple[float, float] | None:
        data = self.coordinator.data.get(self._vehicle_id, {}) if self.coordinator.data else {}
        location = data.get("location")
        if not isinstance(location, dict):
            return None
        coordinates = location.get("location")
        if not isinstance(coordinates, dict) or coordinates.get("validFlag") not in {1, "1"}:
            return None
        latitude = coordinates.get("latitude")
        longitude = coordinates.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            return None
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            return None
        return float(latitude), float(longitude)
