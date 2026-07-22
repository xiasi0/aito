from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APIG_AUTHORIZATION,
    CONF_ASSET_KEY,
    CONF_DEVICE_ID,
    CONF_ENCRYPTED_SESSION_CONTEXT,
    CONF_IVCS_DEVICE_ID,
    CONF_OMP_DEVICE_ID,
    CONF_REFRESH_TOKEN,
    CONF_SERVICE_INFO,
    CONF_SERVICE_USER_INFO,
    CONF_SESSION_KEY,
    CONF_USER_INFO,
    CONF_XID,
)
from .storage import AitoAssetStore

REDACTED = "REDACTED"
REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SESSION_KEY,
    CONF_XID,
    CONF_APIG_AUTHORIZATION,
    CONF_USER_INFO,
    CONF_SERVICE_INFO,
    CONF_SERVICE_USER_INFO,
    CONF_ASSET_KEY,
    CONF_DEVICE_ID,
    CONF_OMP_DEVICE_ID,
    CONF_IVCS_DEVICE_ID,
    CONF_ENCRYPTED_SESSION_CONTEXT,
}
SENSITIVE_KEYS = {
    "authorization",
    "authcode",
    "account_name",
    "accountname",
    "address",
    "avatar",
    "credential_key",
    "cookie",
    "cookies",
    "email",
    "gps",
    "lat",
    "latitude",
    "license_plate",
    "licenseplate",
    "lon",
    "location",
    "longitude",
    "mobile",
    "mobile_number",
    "mobilenumber",
    "mobile_phone",
    "mobilephone",
    "nickname",
    "p256_private_key_pem",
    "p256privatekeypem",
    "password",
    "plate",
    "plate_no",
    "plateno",
    "plate_number",
    "platenumber",
    "phone",
    "phone_number",
    "phonenumber",
    "sessionkey",
    "jsessionid",
    "tgc",
    "token",
    "user_id",
    "userid",
    "vehicleid",
    "vehicleidstr",
    "vehiclename",
    "vin",
    "vincode",
    "xid",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    entry_data = _redact_data(entry.data)
    asset_key = entry.data.get(CONF_ASSET_KEY)
    assets = await AitoAssetStore(hass, asset_key).async_load() if asset_key else {}
    asset_data = _redact_data(assets)
    return {"entry": entry_data, "assets": asset_data}


def _redact_data(value: Any, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {item_key: _redact_data(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact_data(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    compact = normalized.replace("_", "")
    return (
        key in REDACT
        or normalized in SENSITIVE_KEYS
        or compact in SENSITIVE_KEYS
        or "token" in compact
        or "authorization" in compact
        or "password" in compact
        or "privatekey" in compact
        or compact == "tgc"
    )
