from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .const import CONF_DEVICE_ID, CONF_VEHICLES, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

STORAGE_VERSION = 1
MOBILE_NUMBER_KEYS = ("mobileNumber", "mobile_number", "phoneNumber", "phone_number")
TEMPORARY_ASSET_KEY = "pending-login"


def asset_storage_key(asset_key: str) -> str:
    safe_key = _safe_asset_key(asset_key)
    filename = safe_key if safe_key.endswith(".json") else f"{safe_key}.json"
    return f"{DOMAIN}/assets/{filename}"


def _legacy_asset_storage_key(asset_key: str) -> str:
    return f"{DOMAIN}/assets/{_safe_asset_key(asset_key)}"


def temporary_asset_key(_device_id: str) -> str:
    return TEMPORARY_ASSET_KEY


def asset_key_from_login_data(data: dict[str, Any]) -> str:
    mobile_number = _find_first_key(data, MOBILE_NUMBER_KEYS)
    if mobile_number:
        return _safe_asset_key(str(mobile_number))

    vehicles = data.get(CONF_VEHICLES)
    if isinstance(vehicles, list):
        for vehicle in vehicles:
            if not isinstance(vehicle, dict):
                continue
            vehicle_id = vehicle.get("vehicleIdStr") or vehicle.get("vehicleId") or vehicle.get("id")
            if vehicle_id:
                return _safe_asset_key(str(vehicle_id))
    return _safe_asset_key(str(data[CONF_DEVICE_ID]))


def _find_first_key(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            found = value.get(key)
            if found:
                return found
        for nested in value.values():
            found = _find_first_key(nested, keys)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_first_key(nested, keys)
            if found:
                return found
    return None


def _safe_asset_key(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", ".", "+", "@"} else "_" for char in str(value))
    return safe.strip(" .") or "unknown"


class AitoAssetStore:
    def __init__(self, hass: HomeAssistant, asset_key: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store(hass, STORAGE_VERSION, asset_storage_key(asset_key))
        legacy_key = _legacy_asset_storage_key(asset_key)
        self._legacy_store = Store(hass, STORAGE_VERSION, legacy_key) if legacy_key != asset_storage_key(asset_key) else None

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        if isinstance(data, dict):
            return data
        if self._legacy_store is not None:
            legacy_data = await self._legacy_store.async_load()
            if isinstance(legacy_data, dict):
                return legacy_data
        return {}

    async def async_save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)

    async def async_remove(self) -> None:
        await self._store.async_remove()
        if self._legacy_store is not None:
            await self._legacy_store.async_remove()
