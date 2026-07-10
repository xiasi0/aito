from __future__ import annotations

import json
import logging
import uuid
from contextlib import suppress
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .api import AitoApiClient
from .auth import (
    build_huawei_login_url,
    extract_auth_code,
    extract_credentials,
    extract_huawei_omp_auth_code,
    extract_state,
    generate_code_verifier,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APIG_AUTHORIZATION,
    CONF_ASSET_KEY,
    CONF_AUTH_CALLBACK,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_SESSION_KEY,
    CONF_SESSION_KEY_EXPIRE_IN,
    CONF_SERVICE_INFO,
    CONF_SERVICE_LOGIN_STATUS,
    CONF_SERVICE_USER_INFO,
    CONF_USER_INFO,
    CONF_VEHICLES,
    CONF_XID,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    scan_interval_seconds,
)
from .models import Vehicle, firmware_sw_version
from .storage import AitoAssetStore, asset_key_from_login_data, temporary_asset_key

_LOGGER = logging.getLogger(__name__)


class AitoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._state = uuid.uuid4().hex
        self._device_id = uuid.uuid4().hex
        self._code_verifier = generate_code_verifier()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            callback_value = user_input[CONF_AUTH_CALLBACK]
            try:
                auth_code = extract_auth_code(callback_value)
                state = extract_state(callback_value)
                if state and state != self._state:
                    errors["base"] = "state_mismatch"
                else:
                    temp_asset_key = temporary_asset_key(self._device_id)
                    temp_asset_store = AitoAssetStore(self.hass, temp_asset_key)
                    with suppress(Exception):
                        await temp_asset_store.async_remove()
                    await temp_asset_store.async_save({CONF_DEVICE_ID: self._device_id})
                    try:
                        data = await self.hass.async_add_executor_job(self._login, auth_code)
                        if not _has_stored_vehicles(data):
                            _LOGGER.warning("AITO login did not return any vehicles")
                            errors["base"] = "no_vehicles"
                        else:
                            await self.async_set_unique_id(str(data.get(CONF_XID) or data[CONF_DEVICE_ID]))
                            self._abort_if_unique_id_configured()
                            asset_key = asset_key_from_login_data(data)
                            await self._save_and_verify_assets(asset_key, data)
                            return self.async_create_entry(
                                title="AITO",
                                data={CONF_ASSET_KEY: asset_key, CONF_DEVICE_ID: data[CONF_DEVICE_ID]},
                                options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS},
                            )
                    finally:
                        with suppress(Exception):
                            await temp_asset_store.async_remove()
            except ValueError:
                errors["base"] = "invalid_auth_code"
            except Exception:
                _LOGGER.exception("AITO login failed")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_AUTH_CALLBACK): str}),
            errors=errors,
            description_placeholders={
                "login_url": build_huawei_login_url(
                    self._state,
                    code_verifier=self._code_verifier,
                    device_id=self._device_id,
                )
            },
        )

    def _login(self, huawei_code: str) -> dict[str, Any]:
        client = AitoApiClient(apig_verify_ssl=False)
        huawei_response = client.exchange_huawei_authorization_code(
            huawei_code,
            code_verifier=self._code_verifier,
            device_id=self._device_id,
        )
        auth_code = extract_huawei_omp_auth_code(huawei_response)
        if not auth_code:
            raise ValueError("Huawei token response did not return auth code")
        auth_response = client.user_auth(auth_code, device_id=self._device_id)
        credentials = extract_credentials(auth_response)
        xid = credentials.get(CONF_XID)
        if not xid:
            raise RuntimeError(
                "user auth did not return xid: "
                f"credentials={sorted(credentials.keys())}, "
                f"response={_safe_response_summary(auth_response)}"
            )
        user_info = credentials.get(CONF_USER_INFO)
        user_id = user_info.get("userId") if isinstance(user_info, dict) else None
        apig_authorization = self._refresh_vehicle_authorization(
            client,
            xid,
            str(user_id) if user_id else None,
        )
        if not apig_authorization:
            raise ValueError("vehicle authorization not returned")

        client.apig_authorization = apig_authorization
        vehicles = client.apig_vehicles()
        vehicle_items = vehicles if isinstance(vehicles, list) else vehicles.get("data", []) if isinstance(vehicles, dict) else []
        stored_vehicles = []
        for item in vehicle_items:
            if not isinstance(item, dict):
                continue
            stored_vehicle = Vehicle.from_api(item).as_storage()
            if not stored_vehicle.get("vehicleIdStr"):
                continue
            self._attach_current_version(client, stored_vehicle)
            stored_vehicles.append(stored_vehicle)
        return {
            CONF_DEVICE_ID: self._device_id,
            CONF_ACCESS_TOKEN: credentials.get(CONF_ACCESS_TOKEN),
            CONF_REFRESH_TOKEN: credentials.get(CONF_REFRESH_TOKEN),
            CONF_XID: credentials.get(CONF_XID),
            CONF_SESSION_KEY: credentials.get(CONF_SESSION_KEY),
            CONF_SESSION_KEY_EXPIRE_IN: credentials.get(CONF_SESSION_KEY_EXPIRE_IN),
            CONF_USER_INFO: credentials.get(CONF_USER_INFO),
            CONF_SERVICE_INFO: credentials.get(CONF_SERVICE_INFO),
            CONF_SERVICE_USER_INFO: credentials.get(CONF_SERVICE_USER_INFO),
            CONF_SERVICE_LOGIN_STATUS: credentials.get(CONF_SERVICE_LOGIN_STATUS),
            CONF_APIG_AUTHORIZATION: apig_authorization,
            CONF_VEHICLES: stored_vehicles,
        }

    def _refresh_vehicle_authorization(self, client: AitoApiClient, xid: str, user_id: str | None) -> str | None:
        try:
            response = client.vehicle_refresh(
                xid=xid,
                device_id=self._device_id,
                user_id=user_id,
                require_account_id=True,
                aito_service=False,
            )
        except Exception:
            _LOGGER.debug("AITO vehicle authorization refresh during login failed", exc_info=True)
            return None
        if isinstance(response, dict) and response.get("accessToken"):
            return str(response["accessToken"])
        return None

    def _attach_current_version(self, client: AitoApiClient, stored_vehicle: dict[str, Any]) -> None:
        try:
            response = client.firmware_current_version(str(stored_vehicle["vehicleIdStr"]))
        except Exception:
            _LOGGER.debug("AITO firmware version lookup failed during login", exc_info=True)
            return
        version = firmware_sw_version(response)
        if version:
            stored_vehicle["swVersion"] = version

    async def _save_and_verify_assets(self, asset_key: str, data: dict[str, Any]) -> None:
        asset_store = AitoAssetStore(self.hass, asset_key)
        await asset_store.async_save(data)
        saved = await asset_store.async_load()
        if not saved or not _has_stored_vehicles(saved) or not saved.get(CONF_APIG_AUTHORIZATION):
            raise RuntimeError("AITO credential asset save verification failed")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AitoOptionsFlow()


class AitoOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=scan_interval_seconds(self.config_entry.options),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10)),
                }
            ),
        )


def _safe_response_summary(response: Any) -> str:
    if not isinstance(response, dict):
        return type(response).__name__
    safe_fields = (
        "code",
        "resultCode",
        "errorCode",
        "returnCode",
        "msg",
        "message",
        "error",
        "error_description",
    )
    summary = {key: response[key] for key in safe_fields if key in response}
    summary["keys"] = sorted(str(key) for key in response.keys())
    return json.dumps(summary, ensure_ascii=False)


def _has_stored_vehicles(data: dict[str, Any]) -> bool:
    vehicles = data.get(CONF_VEHICLES)
    return isinstance(vehicles, list) and any(isinstance(vehicle, dict) and vehicle.get("vehicleIdStr") for vehicle in vehicles)
