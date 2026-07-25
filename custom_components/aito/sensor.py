from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .models import Vehicle, vehicle_device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    snapshots = data.get("raw_status_snapshots", {})
    async_add_entities(
        AitoRawVehicleStatusSensor(vehicle, snapshots.get(vehicle.id))
        for vehicle in data["vehicles"]
    )


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
