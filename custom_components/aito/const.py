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

CONF_PHONE = "phone"
CONF_PASSWORD = "password"
CONF_SMS_CODE = "sms_code"
CONF_ENCRYPTED_PASSWORD = "encrypted_password"
CONF_ASSET_KEY = "asset_key"
CONF_DEVICE_ID = "device_id"
CONF_OMP_DEVICE_ID = "omp_device_id"
CONF_IVCS_DEVICE_ID = "ivcs_device_id"
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
CONF_ENCRYPTED_SESSION_CONTEXT = "encrypted_session_context"
CONF_VEHICLES = "vehicles"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_SECONDS = 30
MIN_SCAN_INTERVAL_SECONDS = 10

AITO_CLIENT_ID = "104872091"

OMP_BASE_URL = "https://omp.uopes.cn"
APIG_BASE_URL = "https://apig.fgaiservice.com"
DEFAULT_OMP_CLIENT_TYPE = "ios"
DEFAULT_DEVICE_MODEL = "iPhone"
DEFAULT_NATIVE_DEVICE_MODEL = "iPhone8,1"
DEFAULT_APIG_CLIENT_VERSION = "HUAWEI_IVCS_APP_3.002.300"
DEFAULT_USER_AGENT = "XCar-APP-iOS/3.0.2.300 (iPhone; iOS 15.8.8; Scale/2.0)"
DEFAULT_PACKAGE_NAME = "app.huawei.auto"
DEFAULT_VEHICLE_EC = "SERES"


def scan_interval_seconds(options: Mapping[str, Any] | None) -> int:
    try:
        seconds = int((options or {}).get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL_SECONDS
    return max(MIN_SCAN_INTERVAL_SECONDS, seconds)
