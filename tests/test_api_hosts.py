"""Regression tests for Antigravity API host selection."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_const_module():
    const_path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "hass_antigravity_usage"
        / "const.py"
    )
    spec = importlib.util.spec_from_file_location("hass_antigravity_usage_const", const_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ApiHostTest(unittest.TestCase):
    def test_cloud_code_quota_urls_use_daily_host(self) -> None:
        """Match the host used by the Antigravity CLI quota panel."""
        const = _load_const_module()

        self.assertTrue(
            const.LOAD_CODE_ASSIST_URL.startswith("https://daily-cloudcode-pa.googleapis.com/")
        )
        self.assertTrue(
            const.QUOTA_SUMMARY_URL.startswith("https://daily-cloudcode-pa.googleapis.com/")
        )
