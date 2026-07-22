from __future__ import annotations

import asyncio
import json
import sys
import types
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from custom_components.aito.api import AitoApiClient, _urllib_insecure_transport, _urllib_transport
from custom_components.aito.auth import extract_credentials, session_key_status
from custom_components.aito.huawei_auth import HuaweiIosAuthClient
from custom_components.aito.storage import (
    AitoDeviceIdentityStore,
    decrypt_session_context,
    encrypt_session_context,
    identity_account_key,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body))
        if url.endswith("/queryCustomizedPage"):
            return 200, {"Set-Cookie": "HWWAFSESID=waf\nHWWAFSESTIME=time"}, b"{}"
        if "/oauth2/v3/silent_token" in url:
            return 200, {}, b'{"code":"ios-auth-code"}'
        return 200, {}, b"{}"


class MemoryStore:
    values: dict[str, object] = {}

    def __init__(self, hass, version, key) -> None:
        self.key = key

    async def async_load(self):
        return self.values.get(self.key)

    async def async_save(self, value) -> None:
        self.values[self.key] = value


class IosProtocolTests(TestCase):
    def test_apig_tls_exception_does_not_apply_to_omp(self) -> None:
        client = AitoApiClient(apig_verify_ssl=False)

        self.assertIs(client.transport, _urllib_transport)
        self.assertIs(client.apig_transport, _urllib_insecure_transport)

    def test_silent_token_uses_ios_platform_endpoint_and_client(self) -> None:
        transport = RecordingTransport()
        client = HuaweiIosAuthClient(device_id="huawei-device", transport=transport)

        self.assertEqual(client.silent_token("service-token"), "ios-auth-code")

        _, url, _, body = transport.calls[0]
        parsed = urlparse(url)
        self.assertEqual(parsed.netloc, "oauth-login.platform.hicloud.com")
        self.assertEqual(parse_qs(parsed.query)["client_id"], ["104872091"])
        self.assertEqual(parse_qs((body or b"").decode())["device_id"], ["huawei-device"])

    def test_huawei_account_cookies_are_reused_on_account_requests(self) -> None:
        calls: list[dict[str, str]] = []

        def transport(method, url, headers, body, timeout):
            calls.append(headers)
            return 200, {"Set-Cookie": "JSESSIONID=session-cookie\nRiskCookie=risk-cookie"}, b"{}"

        client = HuaweiIosAuthClient(device_id="huawei-device", transport=transport)
        client.request_sms("13000000000")
        client.request_sms("13000000000")

        self.assertEqual(client.jsessionid, "session-cookie")
        self.assertEqual(client.cookies["RiskCookie"], "risk-cookie")
        self.assertIn("JSESSIONID=session-cookie", calls[1]["Cookie"])
        self.assertIn("RiskCookie=risk-cookie", calls[1]["Cookie"])

    def test_omp_and_ivcs_use_their_own_persisted_ids(self) -> None:
        transport = RecordingTransport()
        client = AitoApiClient(
            apig_authorization="vehicle-token",
            ivcs_device_id="ivcs-device",
            transport=transport,
        )

        client.user_auth(
            "ios-auth-code",
            device_id="omp-device",
            device_model="iPhone",
            native_device_model="iPhone8,1",
        )
        client.force_login(
            xid="session-key",
            device_id="omp-device",
            device_model="iPhone",
            native_device_model="iPhone8,1",
            user_id="omp-user",
        )
        client.apig_vehicles()

        _, auth_url, auth_headers, auth_body = transport.calls[1]
        self.assertTrue(auth_url.endswith("/xcar/omp/xbs/account/user/auth"))
        self.assertEqual(json.loads((auth_body or b"{}").decode())["device"]["id"], "omp-device")
        self.assertEqual(auth_headers["deviceModel"], "iPhone8,1")
        self.assertIn("HWWAFSESID=waf", auth_headers["Cookie"])

        _, kickout_url, kickout_headers, kickout_body = transport.calls[2]
        self.assertTrue(kickout_url.endswith("/xcar/omp/xbs/account/user/kickout"))
        self.assertEqual(json.loads((kickout_body or b"{}").decode())["deviceInfo"]["id"], "omp-device")
        self.assertEqual(kickout_headers["xid"], "session-key")
        self.assertEqual(kickout_headers["EC"], "")

        _, _, ivcs_headers, _ = transport.calls[3]
        self.assertEqual(ivcs_headers["X-Device-Id"], "ivcs-device")
        self.assertEqual(ivcs_headers["X-Client-Version"], "HUAWEI_IVCS_APP_3.002.300")

    def test_account_identity_key_is_stable_and_session_context_is_encrypted(self) -> None:
        self.assertEqual(identity_account_key("13000000000"), identity_account_key(" 130-0000-0000 "))
        self.assertNotEqual(identity_account_key("13000000000"), identity_account_key("13100000000"))

        key = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="
        encrypted = encrypt_session_context(
            {"tgc": "service-token", "jsessionid": "session-cookie", "omp_cookies": {"HWWAFSESID": "waf"}},
            key,
        )
        self.assertNotIn("service-token", encrypted)
        self.assertEqual(
            decrypt_session_context(encrypted, key)["omp_cookies"],
            {"HWWAFSESID": "waf"},
        )

    def test_each_phone_account_keeps_its_own_persistent_identity(self) -> None:
        MemoryStore.values = {}
        homeassistant_module = types.ModuleType("homeassistant")
        helpers_module = types.ModuleType("homeassistant.helpers")
        storage_module = types.ModuleType("homeassistant.helpers.storage")
        storage_module.Store = MemoryStore
        with patch.dict(
            sys.modules,
            {
                "homeassistant": homeassistant_module,
                "homeassistant.helpers": helpers_module,
                "homeassistant.helpers.storage": storage_module,
            },
        ):
            store = AitoDeviceIdentityStore(object())
            first = asyncio.run(store.async_get_or_create("13000000000"))
            same_account = asyncio.run(store.async_get_or_create("13000000000"))
            other_account = asyncio.run(store.async_get_or_create("13100000000"))

        self.assertEqual(first["device_id"], same_account["device_id"])
        self.assertEqual(first["omp_device_id"], same_account["omp_device_id"])
        self.assertEqual(first["ivcs_device_id"], same_account["ivcs_device_id"])
        self.assertNotEqual(first["device_id"], other_account["device_id"])
        self.assertNotEqual(first["p256_key_id"], other_account["p256_key_id"])

    def test_session_key_status_is_found_in_nested_omp_response(self) -> None:
        self.assertEqual(session_key_status({"data": {"userInfo": {"sessionKeyStatus": "0"}}}), "0")
        self.assertEqual(session_key_status({"userInfo": {"sessionKeyStatus": 1}}), "1")
        self.assertIsNone(session_key_status({"oauthToken": {"accessToken": "opaque"}}))

    def test_omp_xid_uses_session_key_before_oauth_token_xid(self) -> None:
        credentials = extract_credentials(
            {
                "sessionKey": "omp-session-key",
                "data": {"oauthToken": {"accessToken": "access", "refreshToken": "refresh", "xid": "oauth-xid"}},
            }
        )
        self.assertEqual(credentials["xid"], "omp-session-key")
