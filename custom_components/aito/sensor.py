from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .devices import SensorSpec, value_at_path
from .models import Vehicle, vehicle_device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    snapshots = data.get("raw_status_snapshots", {})
    entities = [
        AitoRawVehicleStatusSensor(vehicle, snapshots.get(vehicle.id))
        for vehicle in data["vehicles"]
    ]
    coordinator = data.get("coordinator")
    if coordinator is not None:
        for vehicle in data["vehicles"]:
            spec = data["vehicle_specs"].get(vehicle.id)
            if spec is not None:
                entities.extend(AitoMappedSensor(coordinator, vehicle, sensor) for sensor in spec.sensors)
    async_add_entities(entities)


class AitoRawVehicleStatusSensor(RestoreEntity, SensorEntity):
    """One-time APIG status snapshot for unsupported vehicle-model research."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "raw_vehicle_status"

    def __init__(self, vehicle: Vehicle, snapshot: dict[str, Any] | None) -> None:
        self._attr_unique_id = f"{vehicle.id}_raw_vehicle_status"
        self._attr_device_info = vehicle_device_info(vehicle)
        self._apply_snapshot(snapshot)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._attr_extra_state_attributes is not None:
            return
        if last_state := await self.async_get_last_state():
            self._attr_native_value = last_state.state
            self._attr_extra_state_attributes = {
                key: value for key, value in last_state.attributes.items() if key != "friendly_name"
            }

    def _apply_snapshot(self, snapshot: dict[str, Any] | None) -> None:
        if snapshot is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
            return
        self._attr_native_value = str(snapshot.get("lastUpdatedAt") or "captured")
        self._attr_extra_state_attributes = snapshot


class AitoMappedSensor(CoordinatorEntity[AitoDataCoordinator], SensorEntity):
    """A sensor explicitly declared for a matching vehicle project."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle, spec: SensorSpec) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle.id
        self._spec = spec
        self._attr_unique_id = f"{vehicle.id}_{spec.key}"
        self._attr_device_info = vehicle_device_info(vehicle)
        self._attr_translation_key = spec.translation_key
        if spec.device_class:
            self._attr_device_class = SensorDeviceClass(spec.device_class)
        if spec.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = spec.native_unit_of_measurement
        if spec.state_class:
            self._attr_state_class = SensorStateClass(spec.state_class)

    @property
    def native_value(self):
        data = self.coordinator.data.get(self._vehicle_id, {}) if self.coordinator.data else {}
        return value_at_path(data, self._spec.path)
