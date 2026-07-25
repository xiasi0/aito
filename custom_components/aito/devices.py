from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Vehicle


@dataclass(frozen=True)
class SensorSpec:
    key: str
    path: tuple[str, ...]
    translation_key: str
    device_class: str | None = None
    native_unit_of_measurement: str | None = None
    state_class: str | None = None


@dataclass(frozen=True)
class VehicleSpec:
    key: str
    enterprise_code: str
    project_code: str
    sensors: tuple[SensorSpec, ...]

    def matches(self, vehicle: Vehicle) -> bool:
        profile = vehicle.profile
        return (
            profile.enterprise_code == self.enterprise_code
            and profile.project_code == self.project_code
        )


DEVICES: tuple[VehicleSpec, ...] = (
    VehicleSpec(
        key="seres_f3",
        enterprise_code="SERES",
        project_code="SERES-F3",
        sensors=(
            SensorSpec(
                key="battery_soc",
                path=("charge", "soc"),
                translation_key="battery_soc",
                device_class="battery",
                native_unit_of_measurement="%",
                state_class="measurement",
            ),
        ),
    ),
    VehicleSpec(
        key="seres_x1",
        enterprise_code="SERES",
        project_code="SERES-X1",
        sensors=(
            SensorSpec(
                key="wltc_remaining_mileage",
                path=("vehicleStatus", "wltcRemainingMileage"),
                translation_key="wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
        ),
    ),
)


def vehicle_spec_for(vehicle: Vehicle) -> VehicleSpec | None:
    return next((spec for spec in DEVICES if spec.matches(vehicle)), None)


def dynamic_sections(spec: VehicleSpec) -> dict[str, int]:
    return {sensor.path[0]: 0 for sensor in spec.sensors}


def value_at_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value
