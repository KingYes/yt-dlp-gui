"""Tests for application updater helpers."""

from __future__ import annotations

from src.updater import is_newer_version, manifest_url_for_tag


class TestUpdater:
    def test_is_newer_version(self) -> None:
        assert is_newer_version("1.2.0", "1.1.2")
        assert not is_newer_version("1.1.2", "1.1.2")
        assert not is_newer_version("1.1.0", "1.1.2")

    def test_manifest_url_for_tag(self) -> None:
        assert manifest_url_for_tag("1.2.0").endswith("/download/v1.2.0/update-manifest.json")
        assert manifest_url_for_tag("v1.2.0").endswith("/download/v1.2.0/update-manifest.json")
