from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import DOMAIN
from .status_fields import BINARY_SENSOR_FIELDS, SENSOR_FIELDS, Path, StatusField


@dataclass(frozen=True)
class Vehicle:
    id: str
    name: str
    vin: str | None = None
    model: str | None = None
    sw_version: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Vehicle":
        vehicle_id = str(data.get("vehicleIdStr") or data.get("vehicleId") or data.get("id") or "")
        vin = data.get("vin") or data.get("vinCode")
        model = data.get("modelName") or data.get("vehicleModel") or data.get("seriesName")
        sw_version = firmware_sw_version(data)
        name = data.get("vehicleName") or data.get("nickname") or model or _fallback_name(vehicle_id)
        return cls(
            id=vehicle_id,
            name=str(name),
            vin=str(vin) if vin else None,
            model=str(model) if model else None,
            sw_version=str(sw_version) if sw_version else None,
        )

    def as_storage(self) -> dict[str, Any]:
        return {
            "vehicleIdStr": self.id,
            "vehicleName": self.name,
            "vin": self.vin,
            "modelName": self.model,
            "swVersion": self.sw_version,
        }


def vehicle_device_info(vehicle: Vehicle) -> dict[str, Any]:
    info: dict[str, Any] = {
        "identifiers": {(DOMAIN, vehicle.id)},
        "name": vehicle.name,
        "manufacturer": "赛力斯",
    }
    if vehicle.sw_version:
        info["sw_version"] = vehicle.sw_version
    return info


def firmware_sw_version(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    version = response.get("swVersion") or response.get("softwareVersion") or response.get("prettyVersion") or response.get("version")
    return str(version) if version else None


# First paths are the names observed in current dynamic-infos payloads/tests.
# Later paths are conservative aliases from app probes or vendor naming variants.
DynamicSensorField = StatusField
DYNAMIC_SENSOR_FIELDS = SENSOR_FIELDS


def normalize_dynamic_info(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in (*DYNAMIC_SENSOR_FIELDS, *BINARY_SENSOR_FIELDS):
        value = _first_path_value(data, field.paths)
        if value is not None:
            result[field.key] = field.normalize(value)
    _normalize_charge_fields(data, result)
    for section in ("door", "window", "tire", "seat", "lamp", "hvac", "fuel", "location"):
        value = data.get(section)
        if value is not None:
            result[section] = value
    return result


def _first_path_value(data: dict[str, Any], paths: tuple[Path, ...]) -> Any:
    for path in paths:
        value = _path_value(data, path)
        if value is not None:
            return value
    return None


def _path_value(data: dict[str, Any], path: Path) -> Any:
    current: Any = data
    for key in path:
        if isinstance(key, int):
            if not isinstance(current, (list, tuple)) or key >= len(current):
                return None
            current = current[key]
        else:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
    return None if isinstance(current, (dict, list)) else current


def _normalize_charge_fields(data: dict[str, Any], result: dict[str, Any]) -> None:
    charge = data.get("charge")
    if not isinstance(charge, dict):
        return

    if _status_is_charging(charge.get("dcChargeStatus")):
        result["charging_status"] = "dc_charging"
        _set_charge_current(result, charge.get("dcChargeCurrent"))
    elif _status_is_charging(charge.get("acChargeStatus")):
        result["charging_status"] = "ac_charging"
        _set_charge_current(result, charge.get("acChargeCurrent"))

    voltage = _positive_number(result.get("charging_voltage"))
    current = _positive_number(result.get("charging_current"))
    power = _positive_number(result.get("charging_power"))
    if power is None and voltage is not None and current is not None:
        result["charging_power"] = voltage * current / 1000


def _status_is_charging(value: Any) -> bool:
    return value == 6 or str(value) == "6"


def _set_charge_current(result: dict[str, Any], value: Any) -> None:
    if value is not None:
        result["charging_current"] = value


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _fallback_name(vehicle_id: str) -> str:
    return f"AITO {vehicle_id[-6:]}" if vehicle_id else "AITO"
