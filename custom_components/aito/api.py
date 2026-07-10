from __future__ import annotations

import json
import ssl
import uuid
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .const import (
    AITO_SERVICE_HEADER_NAME,
    AITO_SERVICE_HEADER_VALUE,
    AITO_CLIENT_ID,
    APIG_BASE_URL,
    DEFAULT_APIG_CLIENT_VERSION,
    DEFAULT_DEVICE_MODEL,
    DEFAULT_HUAWEI_C_VERSION,
    DEFAULT_HUAWEI_HMS_VERSION,
    DEFAULT_HUAWEI_SDK_VERSION,
    DEFAULT_HUAWEI_TOKEN_URL,
    DEFAULT_OMP_CLIENT_TYPE,
    DEFAULT_PACKAGE_NAME,
    DEFAULT_USER_AGENT,
    DEFAULT_VEHICLE_EC,
    HUAWEI_REDIRECT_URI,
    OMP_BASE_URL,
)

JSON = dict[str, Any]
Transport = Callable[[str, str, dict[str, str], bytes | None, float], tuple[int, dict[str, str], bytes]]

DEFAULT_DYNAMIC_INFO_SECTIONS: JSON = {
    "vehicleStatus": 0,
    "location": 0,
    "door": 0,
    "window": 0,
    "tire": 0,
    "seat": 0,
    "lamp": 0,
    "charge": 0,
    "hvac": 0,
    "fuel": 0,
    "welcome": 0,
    "departurePlan": 0,
    "airConditionPlan": 0,
    "warmCoolingBox": 0,
    "sentryPlan": 0,
}


class AitoApiError(RuntimeError):
    def __init__(self, status: int, response: Any) -> None:
        message = f"AITO request failed with HTTP {status}"
        response_summary = _safe_response_summary(response)
        if response_summary:
            message = f"{message}: {response_summary}"
        super().__init__(message)
        self.status = status
        self.response = response


class AitoApiClient:
    def __init__(
        self,
        *,
        omp_base_url: str = OMP_BASE_URL,
        apig_base_url: str = APIG_BASE_URL,
        apig_authorization: str | None = None,
        apig_client_version: str = DEFAULT_APIG_CLIENT_VERSION,
        timeout: float = 20.0,
        transport: Transport | None = None,
        apig_verify_ssl: bool = True,
    ) -> None:
        self.omp_base_url = omp_base_url.rstrip("/")
        self.apig_base_url = apig_base_url.rstrip("/")
        self.apig_authorization = apig_authorization
        self.apig_client_version = apig_client_version
        self.timeout = timeout
        self.transport = transport or _urllib_transport
        self.apig_transport = transport or (_urllib_transport if apig_verify_ssl else _urllib_insecure_transport)

    def user_auth(
        self,
        auth_code: str,
        *,
        device_id: str,
        device_model: str = DEFAULT_DEVICE_MODEL,
        client_type: str = DEFAULT_OMP_CLIENT_TYPE,
        aito_service: bool = False,
    ) -> Any:
        payload: JSON = {
            "authCode": auth_code,
            "clientType": client_type,
            "device": {"type": "1", "id": device_id, "model": device_model},
        }
        return self._post_omp(
            "/xcar/omp/xbs/account/user/auth",
            payload,
            extra_headers=_aito_service_header(aito_service),
        )

    def exchange_huawei_authorization_code(
        self,
        code: str,
        *,
        code_verifier: str,
        device_id: str,
    ) -> Any:
        url = f"{DEFAULT_HUAWEI_TOKEN_URL}?{urlencode({
            'client_id': AITO_CLIENT_ID,
            'cVersion': DEFAULT_HUAWEI_C_VERSION,
            'hms_version': DEFAULT_HUAWEI_HMS_VERSION,
            'sdkVersion': DEFAULT_HUAWEI_SDK_VERSION,
        })}"
        body = urlencode(
            {
                "client_id": AITO_CLIENT_ID,
                "grant_type": "authorization_code",
                "redirect_uri": HUAWEI_REDIRECT_URI,
                "need_code": "true",
                "need_open_uid": "true",
                "supportAlg": "RS256",
                "code": code,
                "code_type": "1",
                "uuid": device_id,
                "device_id": device_id,
                "device_type": "6",
                "package_name": DEFAULT_PACKAGE_NAME,
                "code_verifier": code_verifier,
            }
        ).encode("utf-8")
        return self._request(
            "POST",
            url,
            {"Content-Type": "application/x-www-form-urlencoded"},
            body,
        )

    def refresh_user_token(
        self,
        access_token: str,
        refresh_token: str,
        *,
        device_id: str,
        device_model: str = DEFAULT_DEVICE_MODEL,
        client_type: str = DEFAULT_OMP_CLIENT_TYPE,
        xid: str | None = None,
        ec: str = DEFAULT_VEHICLE_EC,
        user_id: str | None = None,
    ) -> Any:
        payload: JSON = {
            "clientType": client_type,
            "device": {"type": "1", "id": device_id, "model": device_model},
            "at": access_token,
            "rt": refresh_token,
        }
        headers = {"EC": ec, "deviceModel": device_model}
        if xid:
            headers["xid"] = xid
        if user_id:
            headers["uid"] = user_id
        return self._post_omp(
            "/xcar/omp/xbs/account/user/refresh",
            payload,
            extra_headers=headers,
        )

    def vehicle_auth(
        self,
        *,
        xid: str,
        device_id: str,
        device_model: str = DEFAULT_DEVICE_MODEL,
        ec: str = DEFAULT_VEHICLE_EC,
        user_id: str | None = None,
    ) -> Any:
        """Legacy probe endpoint; the HA runtime flow uses vehicle_refresh."""
        payload = {"deviceInfo": {"type": "1", "id": device_id, "model": device_model}}
        headers = {"xid": xid, "EC": ec, "deviceModel": device_model}
        if user_id:
            headers["uid"] = user_id
        return self._post_omp(
            "/xcar/omp/xbs/account/vehicle/auth",
            payload,
            extra_headers=headers,
        )

    def vehicle_refresh(
        self,
        *,
        xid: str,
        device_id: str,
        device_model: str = DEFAULT_DEVICE_MODEL,
        ec: str = DEFAULT_VEHICLE_EC,
        user_id: str | None = None,
        require_account_id: bool = False,
        aito_service: bool = True,
    ) -> Any:
        payload: JSON = {
            "tokenType": 1,
            "deviceInfo": {"type": "1", "id": device_id, "model": device_model},
        }
        if require_account_id:
            payload["requireAccountId"] = True
        headers = {"xid": xid, "EC": ec, "deviceModel": device_model}
        if user_id:
            headers["uid"] = user_id
        headers.update(_aito_service_header(aito_service))
        return self._post_omp(
            "/xcar/omp/xbs/account/vehicle/refresh",
            payload,
            extra_headers=headers,
        )

    def apig_vehicles(self) -> Any:
        return self._request_apig("GET", "/vcam/v1/accounts/vehicles")

    def dynamic_infos(self, vehicle_id: str, sections: JSON | None = None) -> Any:
        return self._request_apig(
            "POST",
            "/vctrl/v2/controls/dynamic-infos",
            dict(DEFAULT_DYNAMIC_INFO_SECTIONS if sections is None else sections),
            vehicle_id=vehicle_id,
        )

    def location(self, vehicle_id: str) -> Any:
        return self._request_apig("GET", "/vcam/v1/find-car/location", vehicle_id=vehicle_id)

    def firmware_current_version(self, vehicle_id: str) -> Any:
        return self._request_apig("GET", "/vota/v1/firmware/current-version", vehicle_id=vehicle_id)

    def _post_omp(self, path: str, payload: JSON, *, extra_headers: dict[str, str] | None = None) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self._request(
            "POST",
            f"{self.omp_base_url}/{path.lstrip('/')}",
            _omp_headers(extra_headers),
            body,
        )

    def _request_apig(
        self,
        method: str,
        path: str,
        payload: JSON | None = None,
        *,
        vehicle_id: str | None = None,
    ) -> Any:
        if not self.apig_authorization:
            raise ValueError("missing APIG authorization")
        body = None if method == "GET" else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        return self._request(
            method,
            f"{self.apig_base_url}/{path.lstrip('/')}",
            _apig_headers(self.apig_authorization, self.apig_client_version, vehicle_id),
            body,
            transport=self.apig_transport,
        )

    def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        *,
        transport: Transport | None = None,
    ) -> Any:
        selected_transport = transport or self.transport
        status, _response_headers, response_body = selected_transport(method, url, headers, body, self.timeout)
        response = _decode_response(response_body)
        if status >= 400:
            raise AitoApiError(status, response)
        return response


def _omp_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "pkgName": DEFAULT_PACKAGE_NAME,
        "traceID": uuid.uuid4().hex,
    }
    if extra_headers:
        headers.update({key: value for key, value in extra_headers.items() if value is not None})
    return headers


def _apig_headers(authorization: str, client_version: str, vehicle_id: str | None) -> dict[str, str]:
    headers = {
        "authorization": authorization,
        "x-client-version": client_version,
        "x-nonce": str(uuid.uuid4()),
        "User-Agent": "libcurl-agent/1.0",
        "Content-Type": "application/json; charset=utf-8",
    }
    if vehicle_id:
        headers["x-vehicle-id"] = vehicle_id
    return headers


def _aito_service_header(enabled: bool) -> dict[str, str]:
    return {AITO_SERVICE_HEADER_NAME: AITO_SERVICE_HEADER_VALUE} if enabled else {}


def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, dict[str, str], bytes]:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def _urllib_insecure_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, dict[str, str], bytes]:
    request = Request(url, data=body, headers=headers, method=method)
    context = ssl._create_unverified_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def _decode_response(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _safe_response_summary(response: Any) -> str:
    if isinstance(response, dict):
        safe_fields = (
            "resultCode",
            "errorCode",
            "returnCode",
            "msg",
            "message",
            "error",
            "error_description",
        )
        summary = {key: response[key] for key in safe_fields if key in response}
        return json.dumps(summary, ensure_ascii=False) if summary else ""
    if isinstance(response, str):
        return f"str response length={len(response)}"
    return ""
