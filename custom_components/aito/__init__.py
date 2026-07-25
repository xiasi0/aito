from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from .const import (
    CONF_DEVICE_ID,
    CONF_ENCRYPTED_PASSWORD,
    CONF_ENCRYPTED_SESSION_CONTEXT,
    CONF_IVCS_DEVICE_ID,
    CONF_OMP_DEVICE_ID,
    CONF_PHONE,
)
from .models import firmware_sw_version
from .storage import decrypt_password, decrypt_session_context

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
    from .const import (
        CONF_APIG_AUTHORIZATION,
        CONF_ASSET_KEY,
        CONF_DEVICE_ID,
        CONF_IVCS_DEVICE_ID,
        CONF_OMP_DEVICE_ID,
        CONF_VEHICLES,
        DOMAIN,
        PLATFORMS,
    )
    from .coordinator import AitoDataCoordinator
    from .models import Vehicle
    from .storage import AitoAssetStore, AitoDeviceIdentityStore, asset_key_from_login_data

    asset_key = entry.data.get(CONF_ASSET_KEY)
    asset_store = AitoAssetStore(hass, asset_key) if asset_key else None
    assets = await asset_store.async_load() if asset_store else entry.data
    if asset_store and not assets:
        _raise_setup_auth_failed("AITO credential asset is missing")
    phone = assets.get(CONF_PHONE) if isinstance(assets, dict) else None
    if not isinstance(phone, str) or not phone:
        _raise_setup_auth_failed("AITO credential asset is missing its account identity")
    try:
        identity_store = AitoDeviceIdentityStore(hass)
        identity = await identity_store.async_get_or_create(phone)
    except ModuleNotFoundError:
        identity_store = None
        identity = {}
    assets_dirty = False
    for key in (CONF_DEVICE_ID, CONF_OMP_DEVICE_ID, CONF_IVCS_DEVICE_ID):
        identity_value = _identity_value(identity, key)
        if identity_value and assets.get(key) != identity_value:
            assets[key] = identity_value
            assets_dirty = True
    if asset_store and assets:
        target_asset_key = asset_key_from_login_data(assets)
        if target_asset_key != asset_key:
            old_asset_store = asset_store
            asset_store = AitoAssetStore(hass, target_asset_key)
            await asset_store.async_save(assets)
            assets_dirty = False
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_ASSET_KEY: target_asset_key},
            )
            await old_asset_store.async_remove()
    if not assets.get(CONF_APIG_AUTHORIZATION):
        _raise_setup_auth_failed("AITO credential asset is incomplete")
    _validate_saved_login_context(
        assets,
        identity,
        require_identity=identity_store is not None,
    )

    vehicle_items = [item for item in assets.get(CONF_VEHICLES, []) if isinstance(item, dict)]
    if not any(Vehicle.from_api(item).id for item in vehicle_items):
        _raise_setup_auth_failed("AITO vehicle list is empty")

    session_context = _saved_session_context(assets, identity)
    client_kwargs = {"apig_authorization": assets.get(CONF_APIG_AUTHORIZATION)}
    ivcs_device_id = _identity_value(identity, CONF_IVCS_DEVICE_ID) or assets.get(CONF_IVCS_DEVICE_ID)
    if ivcs_device_id:
        client_kwargs["ivcs_device_id"] = ivcs_device_id
    omp_cookies = session_context.get("omp_cookies")
    if isinstance(omp_cookies, dict):
        client_kwargs["omp_cookies"] = omp_cookies
    client = AitoApiClient(**client_kwargs, apig_verify_ssl=False)
    if await _async_backfill_vehicle_sw_versions(hass, client, vehicle_items):
        assets_dirty = True
    if assets_dirty and asset_store is not None:
        await asset_store.async_save(assets)
    vehicles = [vehicle for item in vehicle_items for vehicle in (Vehicle.from_api(item),) if vehicle.id]
    coordinator = AitoDataCoordinator(
        hass,
        entry,
        client,
        vehicles,
        assets=assets,
        asset_store=asset_store,
        identity=identity,
        identity_store=identity_store,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "assets": assets,
        "identity": identity,
        "vehicles": vehicles,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .const import DOMAIN, PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
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


def _validate_saved_login_context(
    assets: dict[str, Any],
    identity: dict[str, Any],
    *,
    require_identity: bool,
) -> None:
    required_asset_values = (
        assets.get(CONF_PHONE),
        assets.get(CONF_ENCRYPTED_PASSWORD),
        assets.get(CONF_ENCRYPTED_SESSION_CONTEXT),
    )
    if not all(isinstance(value, str) and value for value in required_asset_values):
        _raise_setup_auth_failed("AITO saved login context is incomplete")
    credential_key = identity.get("credential_key")
    if require_identity and not (isinstance(credential_key, str) and credential_key):
        _raise_setup_auth_failed("AITO saved login context is incomplete")
    if require_identity and not all(
        isinstance(identity.get(key), str) and identity[key]
        for key in (CONF_DEVICE_ID, CONF_OMP_DEVICE_ID, CONF_IVCS_DEVICE_ID, "huawei_user_id")
    ):
        _raise_setup_auth_failed("AITO saved device identity is incomplete")
    if require_identity:
        try:
            decrypt_password(str(assets[CONF_ENCRYPTED_PASSWORD]), str(credential_key))
            session_context = _saved_session_context(assets, identity)
            if not all(isinstance(session_context.get(key), str) and session_context[key] for key in ("tgc", "jsessionid")):
                raise ValueError("saved session context is incomplete")
            if not all(isinstance(session_context.get(key), dict) for key in ("huawei_cookies", "omp_cookies")):
                raise ValueError("saved session cookies are incomplete")
        except Exception:
            _raise_setup_auth_failed("AITO saved login context is invalid")


def _identity_value(identity: dict[str, Any], key: str) -> str | None:
    value = identity.get(key)
    return str(value) if isinstance(value, str) and value else None


def _saved_session_context(assets: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    encrypted_context = assets.get(CONF_ENCRYPTED_SESSION_CONTEXT)
    if not encrypted_context:
        return {}
    credential_key = identity.get("credential_key")
    if not isinstance(encrypted_context, str) or not isinstance(credential_key, str) or not credential_key:
        raise ValueError("saved session context is invalid")
    return decrypt_session_context(encrypted_context, credential_key)


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
