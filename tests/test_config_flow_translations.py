from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase


COMPONENT_DIR = Path(__file__).parents[1] / "custom_components" / "aito"


class ConfigFlowTranslationTests(TestCase):
    def test_login_copy_has_no_browser_callback_flow(self) -> None:
        for path in (
            COMPONENT_DIR / "strings.json",
            COMPONENT_DIR / "translations" / "zh-Hans.json",
        ):
            translation = json.loads(path.read_text(encoding="utf-8"))
            user_step = translation["config"]["step"]["user"]

            self.assertEqual(set(user_step["data"]), {"phone", "password"})
            self.assertNotIn("{login_url}", user_step["description"])
            serialized = json.dumps(translation["config"], ensure_ascii=False)
            self.assertNotIn("auth_callback", serialized)
            self.assertNotIn("xop.xcar.test.vmall.com", serialized)

    def test_source_has_no_legacy_callback_symbols(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in COMPONENT_DIR.glob("*.py"))

        for symbol in (
            "CONF_AUTH_CALLBACK",
            "auth_callback",
            "login_url",
            "build_pkce",
            "HUAWEI_REDIRECT_URI",
            "DEFAULT_HUAWEI_AUTHORIZE_URL",
            "DEFAULT_HUAWEI_TOKEN_URL",
        ):
            self.assertNotIn(symbol, source)
