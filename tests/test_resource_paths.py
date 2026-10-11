import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.utils.paths import get_base_dir, get_resource_path


class ResourcePathTests(unittest.TestCase):
    def test_project_root_contains_assets_and_env(self):
        asset_path = get_resource_path("assets", "icons", "logo.ico")
        env_path = get_resource_path(".env")

        self.assertTrue(asset_path.exists(), msg=f"Expected {asset_path} to exist")
        self.assertTrue(env_path.exists(), msg=f"Expected {env_path} to exist")

    def test_frozen_mode_uses_meipass_for_resources(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", "C:/temp/app", create=True):
            self.assertEqual(get_base_dir(), Path("C:/temp/app"))


if __name__ == "__main__":
    unittest.main()
