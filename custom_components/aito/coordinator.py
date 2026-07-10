from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

try:
    from homeassistant.exceptions import ConfigEntryAuthFailed
except ModuleNotFoundError:
    class ConfigEntryAuthFailed(RuntimeError):
        pass

from .api import AitoApiClient, AitoApiError
from .auth import extract_credentials, is_user_session_kicked
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APIG_AUTHORIZATION,
    CONF_DEVICE_ID,
    CONF_REFRESH_TOKEN,
    CONF_SERVICE_INFO,
    CONF_SERVICE_LOGIN_STATUS,
    CONF_SERVICE_USER_INFO,
    CONF_SESSION_KEY,
    CONF_SESSION_KEY_EXPIRE_IN,
    CONF_USER_INFO,
    CONF_XID,
    DOMAIN,
    scan_interval_seconds,
)
from .models import Vehicle, normalize_dynamic_info

_LOGGER = logging.getLogger(__name__)


class AitoDataCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AitoApiClient,
        vehicles: list[Vehicle],
        assets: dict[str, Any] | None = None,
        asset_store: Any | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval_seconds(entry.options)),
        )
        self.entry = entry
        self.client = client
        self.vehicles = vehicles
        self.assets = assets if assets is not None else {}
        self.asset_store = asset_store

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for vehicle in self.vehicles:
            raw = await self._async_dynamic_infos(vehicle.id)
            result[vehicle.id] = normalize_dynamic_info(raw if isinstance(raw, dict) else {})
        return result

    async def _async_dynamic_infos(self, vehicle_id: str) -> Any:
        try:
            return await self.hass.async_add_executor_job(self.client.dynamic_infos, vehicle_id)
        except AitoApiError as error:
            if not _is_cancelled_apig_token(error):
                raise
            await self._async_refresh_apig_authorization()
            try:
                return await self.hass.async_add_executor_job(self.client.dynamic_infos, vehicle_id)
            except AitoApiError as retry_error:
                if _is_auth_failure(retry_error):
                    raise ConfigEntryAuthFailed("AITO APIG authorization refresh failed") from retry_error
                raise

    async def _async_refresh_apig_authorization(self) -> None:
        assets = await self.hass.async_add_executor_job(self._refresh_apig_authorization)
        if self.asset_store is not None:
            await self.asset_store.async_save(assets)

    def _refresh_apig_authorization(self) -> dict[str, Any]:
        xid = self.assets.get(CONF_XID)
        device_id = self.assets.get(CONF_DEVICE_ID) or self.entry.data.get(CONF_DEVICE_ID)
        if not xid or not device_id:
            raise ConfigEntryAuthFailed("missing xid or device_id for AITO vehicle token refresh")

        user_info = self.assets.get(CONF_USER_INFO)
        user_id = user_info.get("userId") if isinstance(user_info, dict) else None
        response = self._request_vehicle_refresh(str(xid), str(device_id), str(user_id) if user_id else None)
        authorization = _vehicle_refresh_authorization(response)
        if not authorization and _needs_user_session_refresh(response):
            credentials = self._refresh_user_session(str(xid), str(device_id), str(user_id) if user_id else None)
            xid = credentials.get(CONF_XID) or xid
            user_info = self.assets.get(CONF_USER_INFO)
            user_id = user_info.get("userId") if isinstance(user_info, dict) else user_id
            response = self._request_vehicle_refresh(str(xid), str(device_id), str(user_id) if user_id else None)
            authorization = _vehicle_refresh_authorization(response)
        if not authorization:
            raise ConfigEntryAuthFailed("vehicle refresh did not return accessToken")

        self.client.apig_authorization = str(authorization)
        self.assets[CONF_APIG_AUTHORIZATION] = str(authorization)
        return self.assets

    def _request_vehicle_refresh(self, xid: str, device_id: str, user_id: str | None) -> Any:
        try:
            return self.client.vehicle_refresh(
                xid=xid,
                device_id=device_id,
                user_id=user_id,
                require_account_id=True,
                aito_service=False,
            )
        except AitoApiError as error:
            if _is_auth_failure(error):
                raise ConfigEntryAuthFailed("AITO vehicle token refresh failed") from error
            raise

    def _refresh_user_session(self, xid: str, device_id: str, user_id: str | None) -> dict[str, Any]:
        access_token = self.assets.get(CONF_ACCESS_TOKEN)
        refresh_token = self.assets.get(CONF_REFRESH_TOKEN)
        if not access_token or not refresh_token:
            raise ConfigEntryAuthFailed("missing user token for AITO session refresh")

        try:
            response = self.client.refresh_user_token(
                str(access_token),
                str(refresh_token),
                device_id=device_id,
                xid=xid,
                user_id=user_id,
            )
        except AitoApiError as error:
            if error.status in {401, 403}:
                raise ConfigEntryAuthFailed("user session refresh failed") from error
            raise
        if is_user_session_kicked(response):
            raise ConfigEntryAuthFailed("user session was kicked during refresh")
        credentials = extract_credentials(response)
        if not credentials.get(CONF_XID):
            raise ConfigEntryAuthFailed("user refresh did not return xid")

        for key in (
            CONF_ACCESS_TOKEN,
            CONF_REFRESH_TOKEN,
            CONF_XID,
            CONF_SESSION_KEY,
            CONF_SESSION_KEY_EXPIRE_IN,
            CONF_USER_INFO,
            CONF_SERVICE_INFO,
            CONF_SERVICE_USER_INFO,
            CONF_SERVICE_LOGIN_STATUS,
        ):
            if key in credentials:
                self.assets[key] = credentials[key]
        return credentials


def _is_cancelled_apig_token(error: AitoApiError) -> bool:
    response = error.response
    if not isinstance(response, dict):
        return False
    return error.status == 401 and (
        str(response.get("code")) in {"100011", "100012", "100015", "100002"}
        or response.get("msg") in {"Token invalid", "Token already been cancelled"}
    )


def _is_auth_failure(error: AitoApiError) -> bool:
    return error.status in {401, 403}


def _vehicle_refresh_authorization(response: Any) -> str | None:
    if isinstance(response, dict) and response.get("accessToken"):
        return str(response["accessToken"])
    return None


def _needs_user_session_refresh(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    return (
        str(response.get("code")) in {"401", "10011"}
        or str(response.get("resultCode")) in {"1000019", "3001002"}
        or response.get("msg") in {"xid is expired", "not login", "not logged in"}
    )
