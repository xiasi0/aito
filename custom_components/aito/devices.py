from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import Vehicle


@dataclass(frozen=True)
class SensorSpec:
    key: str
    path: tuple[str, ...]
    translation_key: str
    source: str = "dynamic"
    device_class: str | None = None
    native_unit_of_measurement: str | None = None
    state_class: str | None = None
    converter: Callable[[Any], Any] | None = None
    value_getter: Callable[[dict[str, Any]], Any] | None = None


@dataclass(frozen=True)
class VehicleSpec:
    key: str
    enterprise_code: str
    project_code: str
    sensors: tuple[SensorSpec, ...]
    supports_now_departure_plan: bool = False
    supports_sentry_mode: bool = False

    def matches(self, vehicle: Vehicle) -> bool:
        profile = vehicle.profile
        return (
            profile.enterprise_code == self.enterprise_code
            and profile.project_code == self.project_code
        )


def _absolute_number(value: Any) -> float | int | None:
    return abs(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _charge_power_kw(data: dict[str, Any]) -> float | None:
    current = _absolute_number(value_at_path(data, ("charge", "chargeCurrent")))
    voltage = _absolute_number(value_at_path(data, ("charge", "chargeVoltage")))
    if current is None or voltage is None:
        return None
    return round(int(round(current)) * int(round(voltage)) / 1000, 1)


DEVICES: tuple[VehicleSpec, ...] = (
    VehicleSpec(
        key="seres_f3",
        enterprise_code="SERES",
        project_code="SERES-F3",
        supports_now_departure_plan=True,
        supports_sentry_mode=True,
        sensors=(
            SensorSpec(
                key="battery_soc",
                path=("charge", "soc"),
                translation_key="battery_soc",
                device_class="battery",
                native_unit_of_measurement="%",
                state_class="measurement",
            ),
            SensorSpec(
                key="charge_voltage",
                path=("charge", "chargeVoltage"),
                translation_key="charge_voltage",
                device_class="voltage",
                native_unit_of_measurement="V",
                state_class="measurement",
                converter=_absolute_number,
            ),
            SensorSpec(
                key="charge_current",
                path=("charge", "chargeCurrent"),
                translation_key="charge_current",
                device_class="current",
                native_unit_of_measurement="A",
                state_class="measurement",
                converter=_absolute_number,
            ),
            SensorSpec(
                key="charge_power",
                path=("charge",),
                translation_key="charge_power",
                device_class="power",
                native_unit_of_measurement="kW",
                state_class="measurement",
                value_getter=_charge_power_kw,
            ),
            SensorSpec(
                key="remaining_charge_time",
                path=("charge", "remainChargeTime"),
                translation_key="remaining_charge_time",
                device_class="duration",
                native_unit_of_measurement="min",
                state_class="measurement",
            ),
            SensorSpec(
                key="electric_wltc_remaining_mileage",
                path=("charge", "vcuWltcRemainingMileage"),
                translation_key="electric_wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="wltc_remaining_mileage",
                path=("vehicleStatus", "wltcRemainingMileage"),
                translation_key="wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="total_mileage",
                path=("vehicleStatus", "totalMileage"),
                translation_key="total_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="total_increasing",
            ),
            SensorSpec(
                key="fuel_wltc_remaining_mileage",
                path=("fuel", "fuelWltcRemainingMileage"),
                translation_key="fuel_wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="fuel_remaining",
                path=("fuel", "leftPercent"),
                translation_key="fuel_remaining",
                native_unit_of_measurement="%",
                state_class="measurement",
            ),
            SensorSpec(
                key="average_power_consumption",
                path=("energyReport", "total", "avgPowerConsum"),
                translation_key="average_power_consumption",
                source="energy_report",
                native_unit_of_measurement="kWh/100km",
                state_class="measurement",
            ),
            SensorSpec(
                key="average_fuel_consumption",
                path=("energyReport", "total", "avgFuelConsum"),
                translation_key="average_fuel_consumption",
                source="energy_report",
                native_unit_of_measurement="L/100km",
                state_class="measurement",
            ),
        ),
    ),
    VehicleSpec(
        key="seres_x1",
        enterprise_code="SERES",
        project_code="SERES-X1",
        supports_sentry_mode=True,
        sensors=(
            SensorSpec(
                key="battery_soc",
                path=("charge", "soc"),
                translation_key="battery_soc",
                device_class="battery",
                native_unit_of_measurement="%",
                state_class="measurement",
            ),
            SensorSpec(
                key="charge_voltage",
                path=("charge", "chargeVoltage"),
                translation_key="charge_voltage",
                device_class="voltage",
                native_unit_of_measurement="V",
                state_class="measurement",
                converter=_absolute_number,
            ),
            SensorSpec(
                key="charge_current",
                path=("charge", "chargeCurrent"),
                translation_key="charge_current",
                device_class="current",
                native_unit_of_measurement="A",
                state_class="measurement",
                converter=_absolute_number,
            ),
            SensorSpec(
                key="charge_power",
                path=("charge",),
                translation_key="charge_power",
                device_class="power",
                native_unit_of_measurement="kW",
                state_class="measurement",
                value_getter=_charge_power_kw,
            ),
            SensorSpec(
                key="remaining_charge_time",
                path=("charge", "remainChargeTime"),
                translation_key="remaining_charge_time",
                device_class="duration",
                native_unit_of_measurement="min",
                state_class="measurement",
            ),
            SensorSpec(
                key="electric_wltc_remaining_mileage",
                path=("charge", "vcuWltcRemainingMileage"),
                translation_key="electric_wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="wltc_remaining_mileage",
                path=("vehicleStatus", "wltcRemainingMileage"),
                translation_key="wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="total_mileage",
                path=("vehicleStatus", "totalMileage"),
                translation_key="total_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="total_increasing",
            ),
            SensorSpec(
                key="fuel_wltc_remaining_mileage",
                path=("fuel", "fuelWltcRemainingMileage"),
                translation_key="fuel_wltc_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="fuel_remaining",
                path=("fuel", "leftPercent"),
                translation_key="fuel_remaining",
                native_unit_of_measurement="%",
                state_class="measurement",
            ),
            SensorSpec(
                key="average_power_consumption",
                path=("energyReport", "total", "avgPowerConsum"),
                translation_key="average_power_consumption",
                source="energy_report",
                native_unit_of_measurement="kWh/100km",
                state_class="measurement",
            ),
            SensorSpec(
                key="average_fuel_consumption",
                path=("energyReport", "total", "avgFuelConsum"),
                translation_key="average_fuel_consumption",
                source="energy_report",
                native_unit_of_measurement="L/100km",
                state_class="measurement",
            ),
        ),
    ),
)


def vehicle_spec_for(vehicle: Vehicle) -> VehicleSpec | None:
    return next((spec for spec in DEVICES if spec.matches(vehicle)), None)


def dynamic_sections(spec: VehicleSpec) -> dict[str, int]:
    sections = {sensor.path[0]: 0 for sensor in spec.sensors if sensor.source == "dynamic"}
    if spec.supports_now_departure_plan:
        sections["departurePlan"] = 0
    if spec.supports_sentry_mode:
        sections["vehicleStatus"] = 0
    return sections


def has_energy_report_sensors(spec: VehicleSpec) -> bool:
    return any(sensor.source == "energy_report" for sensor in spec.sensors)


def value_at_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def sensor_value(data: dict[str, Any], spec: SensorSpec) -> Any:
    if spec.value_getter is not None:
        return spec.value_getter(data)
    value = value_at_path(data, spec.path)
    return spec.converter(value) if spec.converter is not None else value
