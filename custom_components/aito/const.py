from __future__ import annotations

from typing import Any, Mapping

try:
    from homeassistant.const import Platform
except ModuleNotFoundError:
    Platform = None

DOMAIN = "aito"
PLATFORMS = (
    [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]
    if Platform
    else ["sensor", "binary_sensor", "device_tracker"]
)

CONF_AUTH_CALLBACK = "auth_callback"
CONF_ASSET_KEY = "asset_key"
CONF_DEVICE_ID = "device_id"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SESSION_KEY = "session_key"
CONF_SESSION_KEY_EXPIRE_IN = "session_key_expire_in"
CONF_XID = "xid"
CONF_USER_INFO = "user_info"
CONF_SERVICE_INFO = "service_info"
CONF_SERVICE_USER_INFO = "service_user_info"
CONF_SERVICE_LOGIN_STATUS = "service_login_status"
CONF_APIG_AUTHORIZATION = "apig_authorization"
CONF_APIG_CLIENT_VERSION = "apig_client_version"
CONF_VEHICLES = "vehicles"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_SECONDS = 30

AITO_CLIENT_ID = "104871165"
HUAWEI_REDIRECT_URI = "https://xop.xcar.test.vmall.com/"
DEFAULT_HUAWEI_AUTHORIZE_URL = "https://oauth-login.cloud.huawei.com/oauth2/v3/authorize"
DEFAULT_HUAWEI_TOKEN_URL = "https://oauth-login.cloud.huawei.com/oauth2/v3/token"
DEFAULT_HUAWEI_SDK_VERSION = "6.12.0.302"
DEFAULT_HUAWEI_C_VERSION = f"HwID_{DEFAULT_HUAWEI_SDK_VERSION}"
DEFAULT_HUAWEI_HMS_VERSION = "61200302"
DEFAULT_HUAWEI_SCOPES = (
    "https://www.huawei.com/auth/account/base.profile",
    "https://www.huawei.com/auth/account/mobile.number",
    "https://www.huawei.com/auth/account/country",
    "https://www.huawei.com/auth/account/realname/state",
)

OMP_BASE_URL = "https://omp.uopes.cn"
APIG_BASE_URL = "https://apig.fgaiservice.com"
DEFAULT_OMP_CLIENT_TYPE = "android"
DEFAULT_DEVICE_MODEL = "HUAWEI Mate 60 Pro"
DEFAULT_APIG_CLIENT_VERSION = "3.0.1.320"
DEFAULT_USER_AGENT = f"X-Car-APP-Android-{DEFAULT_APIG_CLIENT_VERSION}"
DEFAULT_PACKAGE_NAME = "app.huawei.auto"
DEFAULT_VEHICLE_EC = "SERES"
AITO_SERVICE_HEADER_NAME = "clientServiceType"
AITO_SERVICE_HEADER_VALUE = "AITO Service"


def scan_interval_seconds(options: Mapping[str, Any] | None) -> int:
    return int((options or {}).get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS))
