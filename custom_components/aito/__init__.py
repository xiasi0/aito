from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from .models import firmware_sw_version

try:
    from homeassistant.exceptions import ConfigEntryAuthFailed
except ModuleNotFoundError:
    class ConfigEntryAuthFailed(RuntimeError):
        pass

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .api import AitoApiClient
    from .const import CONF_APIG_AUTHORIZATION, CONF_ASSET_KEY, CONF_VEHICLES, DOMAIN, PLATFORMS
    from .coordinator import AitoDataCoordinator
    from .models import Vehicle
    from .storage import AitoAssetStore, asset_key_from_login_data

    asset_key = entry.data.get(CONF_ASSET_KEY)
    asset_store = AitoAssetStore(hass, asset_key) if asset_key else None
    assets = await asset_store.async_load() if asset_store else entry.data
    if asset_store and not assets:
        _raise_setup_auth_failed("AITO credential asset is missing")
    if asset_store and assets:
        target_asset_key = asset_key_from_login_data(assets)
        if target_asset_key != asset_key:
            old_asset_store = asset_store
            asset_store = AitoAssetStore(hass, target_asset_key)
            await asset_store.async_save(assets)
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_ASSET_KEY: target_asset_key},
            )
            await old_asset_store.async_remove()
    if not assets.get(CONF_APIG_AUTHORIZATION):
        _raise_setup_auth_failed("AITO credential asset is incomplete")

    vehicle_items = [item for item in assets.get(CONF_VEHICLES, []) if isinstance(item, dict)]
    if not any(Vehicle.from_api(item).id for item in vehicle_items):
        _raise_setup_auth_failed("AITO vehicle list is empty")

    client = AitoApiClient(apig_authorization=assets.get(CONF_APIG_AUTHORIZATION), apig_verify_ssl=False)
    if await _async_backfill_vehicle_sw_versions(hass, client, vehicle_items) and asset_store is not None:
        await asset_store.async_save(assets)
    vehicles = [vehicle for item in vehicle_items for vehicle in (Vehicle.from_api(item),) if vehicle.id]
    coordinator = AitoDataCoordinator(hass, entry, client, vehicles, assets, asset_store)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "assets": assets,
        "vehicles": vehicles,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .const import DOMAIN, PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from .const import CONF_ASSET_KEY
    from .storage import AitoAssetStore

    asset_key = entry.data.get(CONF_ASSET_KEY)
    if asset_key:
        await AitoAssetStore(hass, asset_key).async_remove()


def _raise_setup_auth_failed(message: str) -> None:
    _LOGGER.warning("%s; reconfigure the integration", message)
    raise ConfigEntryAuthFailed(message)


async def _async_backfill_vehicle_sw_versions(
    hass: HomeAssistant,
    client: AitoApiClient,
    vehicle_items: list[dict[str, Any]],
) -> bool:
    updated = False
    for item in vehicle_items:
        existing_version = firmware_sw_version(item)
        if existing_version:
            if not item.get("swVersion"):
                item["swVersion"] = existing_version
                updated = True
            continue

        vehicle_id = item.get("vehicleIdStr") or item.get("vehicleId") or item.get("id")
        if not vehicle_id:
            continue
        try:
            response = await _async_executor_job(hass, client.firmware_current_version, str(vehicle_id))
        except Exception:
            _LOGGER.debug("AITO firmware version lookup failed during setup", exc_info=True)
            continue
        version = firmware_sw_version(response)
        if version:
            item["swVersion"] = version
            updated = True
    return updated


async def _async_executor_job(hass: HomeAssistant, func, *args):
    async_add_executor_job = getattr(hass, "async_add_executor_job", None)
    if async_add_executor_job is not None:
        return await async_add_executor_job(func, *args)
    return func(*args)
