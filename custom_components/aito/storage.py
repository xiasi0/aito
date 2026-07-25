from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, TYPE_CHECKING

from cryptography.fernet import Fernet

from .const import (
    CONF_DEVICE_ID,
    CONF_IVCS_DEVICE_ID,
    CONF_OMP_DEVICE_ID,
    CONF_PHONE,
    DEFAULT_DEVICE_MODEL,
    DEFAULT_NATIVE_DEVICE_MODEL,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ASSET_STORAGE_VERSION = 1
IDENTITY_STORAGE_VERSION = 2
DEVICE_IDENTITY_KEY = f"{DOMAIN}/device_identity.json"
IDENTITY_ACCOUNT_KEY = "identity_account_key"


def asset_storage_key(asset_key: str) -> str:
    safe_key = _safe_asset_key(asset_key)
    filename = safe_key if safe_key.endswith(".json") else f"{safe_key}.json"
    return f"{DOMAIN}/assets/{filename}"


def device_identity_storage_key() -> str:
    return DEVICE_IDENTITY_KEY


def asset_key_from_login_data(data: dict[str, Any]) -> str:
    phone = data.get(CONF_PHONE)
    if not isinstance(phone, str) or not phone:
        raise ValueError("AITO asset data is missing phone")
    return _safe_asset_key(phone)


def _safe_asset_key(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", ".", "+", "@"} else "_" for char in str(value))
    return safe.strip(" .") or "unknown"


def encrypt_password(password: str, credential_key: str) -> str:
    return _encrypt_text(password, credential_key)


def decrypt_password(encrypted_password: str, credential_key: str) -> str:
    return _decrypt_text(encrypted_password, credential_key)


def encrypt_session_context(context: dict[str, Any], credential_key: str) -> str:
    return _encrypt_text(json.dumps(context, ensure_ascii=False, separators=(",", ":")), credential_key)


def decrypt_session_context(encrypted_context: str, credential_key: str) -> dict[str, Any]:
    value = json.loads(_decrypt_text(encrypted_context, credential_key))
    if not isinstance(value, dict):
        raise ValueError("saved session context must be an object")
    return value


def _encrypt_text(value: str, credential_key: str) -> str:
    return Fernet(credential_key.encode("ascii")).encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_text(value: str, credential_key: str) -> str:
    return Fernet(credential_key.encode("ascii")).decrypt(value.encode("ascii")).decode("utf-8")


class AitoAssetStore:
    def __init__(self, hass: HomeAssistant, asset_key: str) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store(hass, ASSET_STORAGE_VERSION, asset_storage_key(asset_key))

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        if isinstance(data, dict):
            return data
        return {}

    async def async_save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)

    async def async_remove(self) -> None:
        await self._store.async_remove()


class AitoDeviceIdentityStore:
    def __init__(self, hass: HomeAssistant) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store(hass, IDENTITY_STORAGE_VERSION, device_identity_storage_key())

    async def async_get_or_create(self, phone: str) -> dict[str, Any]:
        account_key = identity_account_key(phone)
        accounts = _identity_accounts(await self._store.async_load())
        identity = accounts.get(account_key)

        if identity is None:
            identity = _new_identity()
        else:
            identity = dict(identity)

        _ensure_identity_fields(identity)
        identity[IDENTITY_ACCOUNT_KEY] = account_key
        if accounts.get(account_key) != _stored_identity(identity):
            accounts[account_key] = _stored_identity(identity)
            await self._store.async_save({"accounts": accounts})
        return identity

    @staticmethod
    def generate_credential_key() -> str:
        return Fernet.generate_key().decode("ascii")

    async def async_save(self, data: dict[str, Any]) -> None:
        account_key = data.get(IDENTITY_ACCOUNT_KEY)
        if not isinstance(account_key, str) or not account_key:
            raise ValueError("device identity is not bound to an account")
        stored = await self._store.async_load()
        accounts = _identity_accounts(stored)
        accounts[account_key] = _stored_identity(data)
        await self._store.async_save({"accounts": accounts})


def identity_account_key(phone: str) -> str:
    normalized = "".join(char for char in str(phone).strip() if char.isdigit() or char == "+")
    if not normalized:
        raise ValueError("phone is required for device identity")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _identity_accounts(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}
    accounts = data.get("accounts")
    if not isinstance(accounts, dict):
        return {}
    return {str(key): dict(value) for key, value in accounts.items() if isinstance(value, dict)}


def _new_identity() -> dict[str, Any]:
    from .auth import P256KeyPair

    device_id = str(uuid.uuid4()).upper()
    return {
        CONF_DEVICE_ID: device_id,
        CONF_OMP_DEVICE_ID: device_id,
        CONF_IVCS_DEVICE_ID: device_id,
        "device_model": DEFAULT_DEVICE_MODEL,
        "native_device_model": DEFAULT_NATIVE_DEVICE_MODEL,
        "credential_key": AitoDeviceIdentityStore.generate_credential_key(),
        **P256KeyPair.generate().as_storage(),
    }


def _ensure_identity_fields(identity: dict[str, Any]) -> None:
    device_id = identity.get(CONF_DEVICE_ID)
    if not isinstance(device_id, str) or not device_id:
        device_id = str(uuid.uuid4()).upper()
        identity[CONF_DEVICE_ID] = device_id
    for key in (CONF_OMP_DEVICE_ID, CONF_IVCS_DEVICE_ID):
        if not isinstance(identity.get(key), str) or not identity[key]:
            identity[key] = device_id
    if not identity.get("credential_key"):
        identity["credential_key"] = AitoDeviceIdentityStore.generate_credential_key()
    if not all(identity.get(key) for key in ("p256_key_id", "p256_public_key", "p256_private_key_pem")):
        from .auth import P256KeyPair

        identity.update(P256KeyPair.generate().as_storage())
    if not identity.get("device_model"):
        identity["device_model"] = DEFAULT_DEVICE_MODEL
    if not identity.get("native_device_model"):
        identity["native_device_model"] = DEFAULT_NATIVE_DEVICE_MODEL


def _stored_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in identity.items() if key != IDENTITY_ACCOUNT_KEY}
