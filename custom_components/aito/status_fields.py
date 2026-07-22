from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Path = tuple[str | int, ...]
EnumValue = tuple[Any, Any]


@dataclass(frozen=True)
class StatusField:
    key: str
    paths: tuple[Path, ...]
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    enum_values: tuple[EnumValue, ...] = ()
    normalizer: Callable[[Any], Any] | None = None

    @property
    def options(self) -> tuple[Any, ...]:
        return tuple(value for _raw, value in self.enum_values)

    def normalize(self, value: Any) -> Any:
        if self.normalizer is not None:
            return self.normalizer(value)
        if self.state_class == "measurement":
            return _normalize_measurement(value)
        if not self.enum_values:
            return value
        for raw_value, normalized in self.enum_values:
            if value == raw_value or str(value) == str(raw_value):
                return normalized
        return None


def _normalize_measurement(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _normalize_speed(value: Any) -> Any:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return None
    if speed < 0 or speed > 255:
        return None
    return int(speed) if speed.is_integer() else speed


CHARGE_STATUS_VALUES: tuple[EnumValue, ...] = (
    (0, "initial"),
    (1, "connected_not_charging"),
    (2, "ac_charging"),
    (3, "dc_charging"),
    (4, "full"),
    (5, "fault"),
    (6, "charging"),
    (7, "charge_end"),
    (8, "delayed_charging"),
    (9, "charge_connection"),
    (10, "wireless_charging"),
    (11, "super_charging"),
    (12, "ac_charging_preheating"),
    (13, "wireless_charging_preheating"),
    (14, "dc_charging_preheating"),
    (15, "ac_charging_insulating"),
    (16, "wireless_charging_insulating"),
    (17, "dc_charging_insulating"),
    (18, "charging_heating"),
    (25, "scheduled_charging"),
)

TIRE_PRESSURE_STATUS_VALUES: tuple[EnumValue, ...] = (
    (-1, "invalid"),
    (0, "normal"),
    (1, "high_pressure"),
    (2, "low_pressure"),
    (6, "pressure_low"),
)

TIRE_TEMPERATURE_STATUS_VALUES: tuple[EnumValue, ...] = (
    (-1, "invalid"),
    (0, "normal"),
    (1, "high_temperature"),
)

DOOR_OPEN_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
)

TRUNK_OPEN_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
    (3, True),
)

WINDOW_OPEN_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
    (3, True),
)

SUNROOF_OPEN_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
    (2, True),
    (3, True),
    (4, True),
)

LIGHT_ON_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
)

TIRE_SENSOR_LOW_BATTERY_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (2, True),
)

VEHICLE_ONLINE_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
)

VEHICLE_DRIVING_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
    (2, False),
    (13, True),
    (14, True),
    (15, False),
)

HANDBRAKE_ON_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, False),
    (2, True),
)

ALARM_ACTIVE_VALUES: tuple[EnumValue, ...] = (
    (0, False),
    (1, True),
)

VEHICLE_STATUS_VALUES: tuple[EnumValue, ...] = (
    (0, "initial"),
    (1, "started"),
    (2, "stalled"),
)

GEAR_VALUES: tuple[EnumValue, ...] = (
    (0, "n"),
    (13, "r"),
    (14, "d"),
    (15, "p"),
)

POWER_STATUS_VALUES: tuple[EnumValue, ...] = (
    (0, "off"),
    (1, "acc"),
    (2, "on"),
    (3, "start"),
)

RUNNING_STATUS_VALUES: tuple[EnumValue, ...] = (
    (0, "parked"),
    (1, "driving"),
    (2, "preparing"),
)

REMAINING_MILEAGE_MODE_VALUES: tuple[EnumValue, ...] = (
    (1, "wltc"),
    (2, "nedc"),
    (3, "sum"),
    (4, "cltc"),
)

SENSOR_FIELDS: tuple[StatusField, ...] = (
    StatusField(
        "battery_level",
        (("vehicleStatus", "soc"),),
        unit="%",
        device_class="battery",
        state_class="measurement",
    ),
    StatusField(
        "battery_temperature",
        (("charge", "batteryTemp"), ("charge", "batteryTemperature"), ("vehicleStatus", "batteryTemperature")),
        unit="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    StatusField(
        "range",
        (
            ("vehicleStatus", "sumRemainingMileage"),
            ("charge", "vcuSumRemainingMileage"),
            ("vehicleStatus", "remainMileage"),
        ),
        unit="km",
        device_class="distance",
        state_class="measurement",
    ),
    StatusField(
        "electric_range",
        (
            ("vehicleStatus", "cltcRemainingMileage"),
            ("vehicleStatus", "wltcRemainingMileage"),
            ("vehicleStatus", "nedcRemainingMileage"),
            ("charge", "vcuCltcRemainingMileage"),
            ("charge", "vcuWltcRemainingMileage"),
            ("charge", "vcuNedcRemainingMileage"),
            ("vehicleStatus", "electricRemainMileage"),
            ("vehicleStatus", "evRemainMileage"),
            ("vehicleStatus", "pureElectricRange"),
        ),
        unit="km",
        device_class="distance",
        state_class="measurement",
    ),
    StatusField(
        "energy_consumption",
        (
            ("vehicleStatus", "avgPowerConsumption"),
            ("vehicleStatus", "totalAvgPowerConsumption"),
            ("vehicleStatus", "avgEgyCnse"),
            ("vehicleStatus", "energyConsumption"),
            ("vehicleStatus", "avgEnergyConsumption"),
            ("vehicleStatus", "averageEnergyConsumption"),
            ("charge", "energyConsumption"),
        ),
        unit="kWh/100km",
        state_class="measurement",
    ),
    StatusField(
        "fuel_level",
        (("fuel", "leftPercent"), ("fuel", "fuelLevel"), ("fuel", "fuelPercent"), ("fuel", "oilPercent")),
        unit="%",
        state_class="measurement",
    ),
    StatusField(
        "fuel_range",
        (
            ("fuel", "fuelSumRemainingMileage"),
            ("fuel", "fuelCltcRemainingMileage"),
            ("fuel", "fuelWltcRemainingMileage"),
            ("fuel", "fuelNedcRemainingMileage"),
            ("fuel", "remainMileage"),
            ("fuel", "fuelRemainMileage"),
            ("fuel", "range"),
        ),
        unit="km",
        device_class="distance",
        state_class="measurement",
    ),
    StatusField(
        "charging_status",
        (("charge", "chargeStatus"), ("charge", "chargingStatus")),
        device_class="enum",
        enum_values=CHARGE_STATUS_VALUES,
    ),
    StatusField(
        "charger_connected",
        (
            ("charge", "dcChargeGunConnectStatus"),
            ("charge", "chargeConStatus"),
            ("charge", "chargerConnected"),
            ("charge", "chargingGunConnected"),
        ),
    ),
    StatusField(
        "charge_remaining_time",
        (
            ("charge", "remainChargeTime"),
            ("charge", "chargeRemainingTime"),
            ("charge", "chargingRemainingTime"),
            ("charge", "remainingTime"),
        ),
        unit="min",
        device_class="duration",
        state_class="measurement",
    ),
    StatusField(
        "charging_power",
        (("charge", "chargePower"), ("charge", "chargingPower"), ("charge", "power")),
        unit="kW",
        device_class="power",
        state_class="measurement",
    ),
    StatusField(
        "charging_voltage",
        (("charge", "chargeVoltage"), ("charge", "chargingVoltage"), ("charge", "voltage")),
        unit="V",
        device_class="voltage",
        state_class="measurement",
    ),
    StatusField(
        "charging_current",
        (("charge", "chargeCurrent"), ("charge", "chargingCurrent"), ("charge", "current")),
        unit="A",
        device_class="current",
        state_class="measurement",
    ),
    StatusField(
        "front_left_tire_pressure",
        (
            ("tire", "leftFront", "pressure"),
            ("tire", "leftFront", "tirePressure"),
            ("tire", "leftFrontTirePressure"),
            ("tire", "frontLeftTirePressure"),
        ),
        unit="kPa",
        device_class="pressure",
        state_class="measurement",
    ),
    StatusField(
        "front_right_tire_pressure",
        (
            ("tire", "rightFront", "pressure"),
            ("tire", "rightFront", "tirePressure"),
            ("tire", "rightFrontTirePressure"),
            ("tire", "frontRightTirePressure"),
        ),
        unit="kPa",
        device_class="pressure",
        state_class="measurement",
    ),
    StatusField(
        "rear_left_tire_pressure",
        (
            ("tire", "leftBack", "pressure"),
            ("tire", "leftBack", "tirePressure"),
            ("tire", "leftRearTirePressure"),
            ("tire", "rearLeftTirePressure"),
        ),
        unit="kPa",
        device_class="pressure",
        state_class="measurement",
    ),
    StatusField(
        "rear_right_tire_pressure",
        (
            ("tire", "rightBack", "pressure"),
            ("tire", "rightBack", "tirePressure"),
            ("tire", "rightRearTirePressure"),
            ("tire", "rearRightTirePressure"),
        ),
        unit="kPa",
        device_class="pressure",
        state_class="measurement",
    ),
    StatusField(
        "front_left_tire_status",
        (
            ("tire", "leftFront", "status"),
            ("tire", "leftFront", "tireStatus"),
            ("tire", "leftFrontTireStatus"),
            ("tire", "frontLeftTireStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_PRESSURE_STATUS_VALUES,
    ),
    StatusField(
        "front_right_tire_status",
        (
            ("tire", "rightFront", "status"),
            ("tire", "rightFront", "tireStatus"),
            ("tire", "rightFrontTireStatus"),
            ("tire", "frontRightTireStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_PRESSURE_STATUS_VALUES,
    ),
    StatusField(
        "rear_left_tire_status",
        (
            ("tire", "leftBack", "status"),
            ("tire", "leftBack", "tireStatus"),
            ("tire", "leftRearTireStatus"),
            ("tire", "rearLeftTireStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_PRESSURE_STATUS_VALUES,
    ),
    StatusField(
        "rear_right_tire_status",
        (
            ("tire", "rightBack", "status"),
            ("tire", "rightBack", "tireStatus"),
            ("tire", "rightRearTireStatus"),
            ("tire", "rearRightTireStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_PRESSURE_STATUS_VALUES,
    ),
    StatusField(
        "tire_status",
        (("tire", "tireStatus"), ("tire", "status")),
        device_class="enum",
        enum_values=TIRE_PRESSURE_STATUS_VALUES,
    ),
    StatusField(
        "front_left_tire_temperature",
        (
            ("tire", "leftFront", "tempture"),
            ("tire", "leftFront", "temperature"),
            ("tire", "leftFront", "tireTemperature"),
            ("tire", "leftFrontTireTemperature"),
            ("tire", "frontLeftTireTemperature"),
        ),
        unit="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    StatusField(
        "front_right_tire_temperature",
        (
            ("tire", "rightFront", "tempture"),
            ("tire", "rightFront", "temperature"),
            ("tire", "rightFront", "tireTemperature"),
            ("tire", "rightFrontTireTemperature"),
            ("tire", "frontRightTireTemperature"),
        ),
        unit="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    StatusField(
        "rear_left_tire_temperature",
        (
            ("tire", "leftBack", "tempture"),
            ("tire", "leftBack", "temperature"),
            ("tire", "leftBack", "tireTemperature"),
            ("tire", "leftRearTireTemperature"),
            ("tire", "rearLeftTireTemperature"),
        ),
        unit="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    StatusField(
        "rear_right_tire_temperature",
        (
            ("tire", "rightBack", "tempture"),
            ("tire", "rightBack", "temperature"),
            ("tire", "rightBack", "tireTemperature"),
            ("tire", "rightRearTireTemperature"),
            ("tire", "rearRightTireTemperature"),
        ),
        unit="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    StatusField(
        "front_left_tire_temperature_status",
        (
            ("tire", "leftFront", "temptureSts"),
            ("tire", "leftFront", "temperatureStatus"),
            ("tire", "leftFrontTireTemperatureStatus"),
            ("tire", "frontLeftTireTemperatureStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_TEMPERATURE_STATUS_VALUES,
    ),
    StatusField(
        "front_right_tire_temperature_status",
        (
            ("tire", "rightFront", "temptureSts"),
            ("tire", "rightFront", "temperatureStatus"),
            ("tire", "rightFrontTireTemperatureStatus"),
            ("tire", "frontRightTireTemperatureStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_TEMPERATURE_STATUS_VALUES,
    ),
    StatusField(
        "rear_left_tire_temperature_status",
        (
            ("tire", "leftBack", "temptureSts"),
            ("tire", "leftBack", "temperatureStatus"),
            ("tire", "leftRearTireTemperatureStatus"),
            ("tire", "rearLeftTireTemperatureStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_TEMPERATURE_STATUS_VALUES,
    ),
    StatusField(
        "rear_right_tire_temperature_status",
        (
            ("tire", "rightBack", "temptureSts"),
            ("tire", "rightBack", "temperatureStatus"),
            ("tire", "rightRearTireTemperatureStatus"),
            ("tire", "rearRightTireTemperatureStatus"),
        ),
        device_class="enum",
        enum_values=TIRE_TEMPERATURE_STATUS_VALUES,
    ),
    StatusField(
        "vehicle_status",
        (("vehicleStatus", "status"),),
        device_class="enum",
        enum_values=VEHICLE_STATUS_VALUES,
    ),
    StatusField(
        "speed",
        (("vehicleStatus", "speed"), ("location", "speed")),
        unit="km/h",
        device_class="speed",
        state_class="measurement",
        normalizer=_normalize_speed,
    ),
    StatusField(
        "gear",
        (("vehicleStatus", "gearSignal"),),
        device_class="enum",
        enum_values=GEAR_VALUES,
    ),
    StatusField(
        "power_status",
        (("vehicleStatus", "powerStatus"), ("location", "powerStatus")),
        device_class="enum",
        enum_values=POWER_STATUS_VALUES,
    ),
    StatusField(
        "running_status",
        (("vehicleStatus", "runningStatus"),),
        device_class="enum",
        enum_values=RUNNING_STATUS_VALUES,
    ),
    StatusField(
        "remaining_mileage_mode",
        (("vehicleStatus", "remainingMimode"), ("vehicleStatus", "remainingMileageMode")),
        device_class="enum",
        enum_values=REMAINING_MILEAGE_MODE_VALUES,
    ),
)

BINARY_SENSOR_FIELDS: tuple[StatusField, ...] = (
    StatusField(
        "front_left_door_open",
        (("door", "doors", 0), ("door", "leftFrontDoor"), ("door", "frontLeftDoor")),
        device_class="door",
        enum_values=DOOR_OPEN_VALUES,
    ),
    StatusField(
        "front_right_door_open",
        (("door", "doors", 1), ("door", "rightFrontDoor"), ("door", "frontRightDoor")),
        device_class="door",
        enum_values=DOOR_OPEN_VALUES,
    ),
    StatusField(
        "rear_left_door_open",
        (("door", "doors", 2), ("door", "leftRearDoor"), ("door", "rearLeftDoor")),
        device_class="door",
        enum_values=DOOR_OPEN_VALUES,
    ),
    StatusField(
        "rear_right_door_open",
        (("door", "doors", 3), ("door", "rightRearDoor"), ("door", "rearRightDoor")),
        device_class="door",
        enum_values=DOOR_OPEN_VALUES,
    ),
    StatusField(
        "trunk_open",
        (("door", "trunk"),),
        device_class="opening",
        enum_values=TRUNK_OPEN_VALUES,
    ),
    StatusField(
        "front_hood_open",
        (("door", "frondHood"), ("door", "frontHood")),
        device_class="opening",
        enum_values=DOOR_OPEN_VALUES,
    ),
    StatusField(
        "charge_port_door_open",
        (("door", "chargeHood"), ("door", "chargePortDoor")),
        device_class="opening",
        enum_values=DOOR_OPEN_VALUES,
    ),
    StatusField(
        "front_left_window_open",
        (("window", "windows", 0), ("window", "leftFrontWindow"), ("window", "frontLeftWindow")),
        device_class="window",
        enum_values=WINDOW_OPEN_VALUES,
    ),
    StatusField(
        "front_right_window_open",
        (("window", "windows", 1), ("window", "rightFrontWindow"), ("window", "frontRightWindow")),
        device_class="window",
        enum_values=WINDOW_OPEN_VALUES,
    ),
    StatusField(
        "rear_left_window_open",
        (("window", "windows", 2), ("window", "leftRearWindow"), ("window", "rearLeftWindow")),
        device_class="window",
        enum_values=WINDOW_OPEN_VALUES,
    ),
    StatusField(
        "rear_right_window_open",
        (("window", "windows", 3), ("window", "rightRearWindow"), ("window", "rearRightWindow")),
        device_class="window",
        enum_values=WINDOW_OPEN_VALUES,
    ),
    StatusField(
        "sunroof_open",
        (("window", "sunroof"),),
        device_class="window",
        enum_values=SUNROOF_OPEN_VALUES,
    ),
    StatusField(
        "high_beam_on",
        (("lamp", "highBeam"),),
        device_class="light",
        enum_values=LIGHT_ON_VALUES,
    ),
    StatusField(
        "low_beam_on",
        (("lamp", "lowBeam"),),
        device_class="light",
        enum_values=LIGHT_ON_VALUES,
    ),
    StatusField(
        "position_lamp_on",
        (("lamp", "positionLamp"),),
        device_class="light",
        enum_values=LIGHT_ON_VALUES,
    ),
    StatusField(
        "front_left_tire_sensor_low_battery",
        (
            ("tire", "leftFront", "sensorStatus"),
            ("tire", "leftFrontSensorStatus"),
            ("tire", "frontLeftTireSensorStatus"),
        ),
        device_class="battery",
        enum_values=TIRE_SENSOR_LOW_BATTERY_VALUES,
    ),
    StatusField(
        "front_right_tire_sensor_low_battery",
        (
            ("tire", "rightFront", "sensorStatus"),
            ("tire", "rightFrontSensorStatus"),
            ("tire", "frontRightTireSensorStatus"),
        ),
        device_class="battery",
        enum_values=TIRE_SENSOR_LOW_BATTERY_VALUES,
    ),
    StatusField(
        "rear_left_tire_sensor_low_battery",
        (
            ("tire", "leftBack", "sensorStatus"),
            ("tire", "leftRearTireSensorStatus"),
            ("tire", "rearLeftTireSensorStatus"),
        ),
        device_class="battery",
        enum_values=TIRE_SENSOR_LOW_BATTERY_VALUES,
    ),
    StatusField(
        "rear_right_tire_sensor_low_battery",
        (
            ("tire", "rightBack", "sensorStatus"),
            ("tire", "rightRearTireSensorStatus"),
            ("tire", "rearRightTireSensorStatus"),
        ),
        device_class="battery",
        enum_values=TIRE_SENSOR_LOW_BATTERY_VALUES,
    ),
    StatusField(
        "vehicle_online",
        (("vehicleStatus", "connectStatus"),),
        device_class="connectivity",
        enum_values=VEHICLE_ONLINE_VALUES,
    ),
    StatusField(
        "vehicle_driving",
        (("vehicleStatus", "runningStatus"), ("vehicleStatus", "gearSignal")),
        device_class="moving",
        enum_values=VEHICLE_DRIVING_VALUES,
    ),
    StatusField(
        "handbrake_on",
        (("vehicleStatus", "epbSts"),),
        enum_values=HANDBRAKE_ON_VALUES,
    ),
    StatusField(
        "alarm_active",
        (("vehicleStatus", "alarmStatus"),),
        device_class="problem",
        enum_values=ALARM_ACTIVE_VALUES,
    ),
)
