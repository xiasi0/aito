from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AitoDataCoordinator
from .models import Vehicle, vehicle_device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.get("coordinator")
    if coordinator is None:
        return
    entities = []
    for vehicle in data["vehicles"]:
        spec = data["vehicle_specs"].get(vehicle.id)
        if spec is None:
            continue
        if spec.supports_now_departure_plan:
            entities.append(AitoNowDeparturePlanSwitch(coordinator, vehicle))
        if spec.supports_sentry_mode:
            entities.append(AitoSentryModeSwitch(coordinator, vehicle))
    async_add_entities(entities)


class AitoNowDeparturePlanSwitch(CoordinatorEntity[AitoDataCoordinator], SwitchEntity):
    """Start or stop the vehicle's App-configured immediate departure plan."""

    _attr_has_entity_name = True
    _attr_translation_key = "now_departure_plan"

    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle.id
        self._attr_unique_id = f"{vehicle.id}_now_departure_plan"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def available(self) -> bool:
        return super().available and self._plan is not None

    @property
    def is_on(self) -> bool | None:
        plan = self._plan
        if plan is None:
            return None
        status = plan.get("planStatus")
        if status is None:
            return None
        return status in {0, "0"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_control_now_departure_plan(self._vehicle_id, enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_control_now_departure_plan(self._vehicle_id, enabled=False)

    @property
    def _plan(self) -> dict[str, Any] | None:
        data = self.coordinator.data.get(self._vehicle_id, {}) if self.coordinator.data else {}
        departure_plan = data.get("departurePlan")
        if not isinstance(departure_plan, dict):
            return None
        plans = departure_plan.get("departurePlanList")
        if not isinstance(plans, list):
            return None
        return next(
            (plan for plan in plans if isinstance(plan, dict) and plan.get("planId") in {0, "0"}),
            None,
        )


class AitoSentryModeSwitch(CoordinatorEntity[AitoDataCoordinator], SwitchEntity):
    """Enable or disable the vehicle's immediate sentry mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "sentry_mode"

    def __init__(self, coordinator: AitoDataCoordinator, vehicle: Vehicle) -> None:
        super().__init__(coordinator)
        self._vehicle_id = vehicle.id
        self._attr_unique_id = f"{vehicle.id}_sentry_mode"
        self._attr_device_info = vehicle_device_info(vehicle)

    @property
    def available(self) -> bool:
        return super().available and self._status is not None

    @property
    def is_on(self) -> bool | None:
        status = self._status
        if status is None:
            return None
        return status in {1, "1", 2, "2"}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self._status
        return {"sentry_mode_status": status} if status is not None else {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_control_sentry_mode(self._vehicle_id, enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_control_sentry_mode(self._vehicle_id, enabled=False)

    @property
    def _status(self) -> Any:
        data = self.coordinator.data.get(self._vehicle_id, {}) if self.coordinator.data else {}
        vehicle_status = data.get("vehicleStatus")
        return vehicle_status.get("sentryModeStatus") if isinstance(vehicle_status, dict) else None
