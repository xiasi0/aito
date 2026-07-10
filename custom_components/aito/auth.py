from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from .const import (
    AITO_CLIENT_ID,
    DEFAULT_HUAWEI_C_VERSION,
    DEFAULT_HUAWEI_AUTHORIZE_URL,
    DEFAULT_HUAWEI_SCOPES,
    HUAWEI_REDIRECT_URI,
)


def generate_code_verifier() -> str:
    return secrets.token_urlsafe(48)


def pkce_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ISO_8859_1")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_huawei_login_url(
    state: str | None = None,
    *,
    code_verifier: str,
    device_id: str,
) -> str:
    resolved_state = state or uuid.uuid4().hex
    params = {
        "access_type": "offline",
        "response_type": "code",
        "client_id": AITO_CLIENT_ID,
        "ui_locales": "zh-cn",
        "redirect_uri": HUAWEI_REDIRECT_URI,
        "scope": "openid " + " ".join(DEFAULT_HUAWEI_SCOPES),
        "display": "touch",
        "nonce": resolved_state,
        "include_granted_scopes": "true",
        "uuid": device_id,
        "reqClientType": "7",
        "loginChannel": "7000000",
        "cVersion": DEFAULT_HUAWEI_C_VERSION,
        "code_challenge": pkce_code_challenge(code_verifier),
        "code_challenge_method": "S256",
        "terminal-type": "unknown",
        "state": resolved_state,
    }
    return f"{DEFAULT_HUAWEI_AUTHORIZE_URL}?{urlencode(params)}"


def extract_auth_code(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("callback does not contain code")
    parsed = urlparse(text)
    if not parsed.scheme:
        return text

    for raw_params in (parsed.query, parsed.fragment):
        params = parse_qs(raw_params)
        for key in ("code", "authCode"):
            values = params.get(key)
            if values and values[0]:
                return values[0]
    raise ValueError("callback does not contain code")


def extract_huawei_omp_auth_code(response: Any) -> str | None:
    if isinstance(response, dict):
        for key in ("serverAuthCode", "authorizationCode", "authCode", "code"):
            value = response.get(key)
            if isinstance(value, str) and value:
                if "://" in value:
                    try:
                        return extract_auth_code(value)
                    except ValueError:
                        pass
                return value
        for value in response.values():
            found = extract_huawei_omp_auth_code(value)
            if found:
                return found
    if isinstance(response, list):
        for value in response:
            found = extract_huawei_omp_auth_code(value)
            if found:
                return found
    return None


def extract_state(value: str) -> str | None:
    parsed = urlparse(value.strip())
    for raw_params in (parsed.query, parsed.fragment):
        values = parse_qs(raw_params).get("state")
        if values and values[0]:
            return values[0]
    return None


def extract_credentials(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    token_source = response.get("oauthToken") if isinstance(response.get("oauthToken"), dict) else response
    result = {
        "access_token": token_source.get("accessToken"),
        "refresh_token": token_source.get("refreshToken"),
        "xid": token_source.get("xid") or response.get("sessionKey"),
        "session_key": response.get("sessionKey"),
        "session_key_expire_in": response.get("sessionKeyExpireIn"),
        "user_info": response.get("userInfo"),
        "service_info": response.get("serviceInfo"),
        "service_user_info": response.get("serviceUserInfo"),
        "service_login_status": response.get("serviceLoginStatus"),
    }
    found = {key: value for key, value in result.items() if value is not None}
    if found.get("access_token") and found.get("refresh_token") and found.get("xid"):
        return found

    best = found
    for value in response.values():
        nested = extract_credentials(value)
        if nested:
            merged = {**found, **nested}
            if merged.get("access_token") and merged.get("refresh_token") and merged.get("xid"):
                return merged
            if len(merged) > len(best):
                best = merged
    return best


def is_user_session_kicked(response: Any) -> bool:
    if isinstance(response, dict):
        user_info = response.get("userInfo")
        if isinstance(user_info, dict) and str(user_info.get("sessionKeyStatus")) == "1":
            return True
        return any(is_user_session_kicked(value) for value in response.values())
    if isinstance(response, list):
        return any(is_user_session_kicked(value) for value in response)
    return False


def extract_vehicle_authorization(response: Any, enterprise_code: str = "SERES") -> str | None:
    for token in _find_vehicle_tokens(response):
        if not isinstance(token, dict):
            continue
        if token.get("enterpriseCode") == enterprise_code and token.get("accessToken"):
            return str(token["accessToken"])
    return None


def _find_vehicle_tokens(value: Any) -> list[Any]:
    if isinstance(value, dict):
        token_list = value.get("vehicleTokenInfoList")
        if isinstance(token_list, list):
            return token_list
        for nested in value.values():
            found = _find_vehicle_tokens(nested)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_vehicle_tokens(nested)
            if found:
                return found
    return []
