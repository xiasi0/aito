from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    # Keep the previous reading when the vehicle stops reporting (returns None)
    # instead of dropping to unknown — tire pressure is only sent while awake.
    sticky: bool = False


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


def _positive_number(value: Any) -> float | int | None:
    """Drop the -1 placeholder the APIG reports while the vehicle sleeps."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _tenths(value: Any) -> float | None:
    """Convert the APIG tenth-degree temperatures (297) into Celsius (29.7)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(value / 10, 1)
    return None


_CHARGE_STATUS_TEXT = {0: "未充电", 1: "充电中", 2: "充电完成", 3: "充电故障", 4: "充电暂停"}


def _charge_status_text(value: Any) -> str | None:
    if value is None:
        return None
    try:
        status = int(value)
    except (TypeError, ValueError):
        return None
    return _CHARGE_STATUS_TEXT.get(status, f"未知({status})")


def _epoch_millis(value: Any) -> datetime | None:
    """Convert the APIG millisecond timestamps into an aware datetime."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return None


def _parking_text(value: Any) -> str | None:
    """Report the electric park brake as the parked or driving state."""
    if value is None:
        return None
    try:
        return "停泊" if int(value) == 2 else "行驶"
    except (TypeError, ValueError):
        return None


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
            SensorSpec(
                key="sum_remaining_mileage",
                path=("vehicleStatus", "sumRemainingMileage"),
                translation_key="sum_remaining_mileage",
                device_class="distance",
                native_unit_of_measurement="km",
                state_class="measurement",
            ),
            SensorSpec(
                key="last_updated_at",
                path=("vehicleStatus", "lastUpdatedAt"),
                translation_key="last_updated_at",
                device_class="timestamp",
                converter=_epoch_millis,
            ),
            SensorSpec(
                key="last_online_at",
                path=("vehicleStatus", "lastOnlineAt"),
                translation_key="last_online_at",
                device_class="timestamp",
                converter=_epoch_millis,
            ),
            SensorSpec(
                key="charge_status",
                path=("charge", "chargeStatus"),
                translation_key="charge_status",
                converter=_charge_status_text,
            ),
            SensorSpec(
                key="parking_status",
                path=("vehicleStatus", "epbSts"),
                translation_key="parking_status",
                converter=_parking_text,
            ),
            SensorSpec(
                key="inside_temperature",
                path=("hvac", "insideTemp"),
                translation_key="inside_temperature",
                device_class="temperature",
                native_unit_of_measurement="°C",
                state_class="measurement",
                converter=_tenths,
            ),
            SensorSpec(
                key="air_conditioner_target_temperature",
                path=("hvac", "remoteTemp"),
                translation_key="air_conditioner_target_temperature",
                device_class="temperature",
                native_unit_of_measurement="°C",
                state_class="measurement",
                converter=_tenths,
            ),
            SensorSpec(
                key="tire_pressure_left_front",
                path=("tire", "leftFront", "pressure"),
                translation_key="tire_pressure_left_front",
                device_class="pressure",
                native_unit_of_measurement="bar",
                state_class="measurement",
                converter=_positive_number,
                sticky=True,
            ),
            SensorSpec(
                key="tire_pressure_right_front",
                path=("tire", "rightFront", "pressure"),
                translation_key="tire_pressure_right_front",
                device_class="pressure",
                native_unit_of_measurement="bar",
                state_class="measurement",
                converter=_positive_number,
                sticky=True,
            ),
            SensorSpec(
                key="tire_pressure_left_back",
                path=("tire", "leftBack", "pressure"),
                translation_key="tire_pressure_left_back",
                device_class="pressure",
                native_unit_of_measurement="bar",
                state_class="measurement",
                converter=_positive_number,
                sticky=True,
            ),
            SensorSpec(
                key="tire_pressure_right_back",
                path=("tire", "rightBack", "pressure"),
                translation_key="tire_pressure_right_back",
                device_class="pressure",
                native_unit_of_measurement="bar",
                state_class="measurement",
                converter=_positive_number,
                sticky=True,
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
