"""Tests for application updater helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.updater import (
    can_apply_in_app_update,
    finalize_pending_manifest,
    is_newer_version,
    manifest_url_for_tag,
)


class TestUpdater:
    def test_is_newer_version(self) -> None:
        assert is_newer_version("1.2.0", "1.1.2")
        assert not is_newer_version("1.1.2", "1.1.2")
        assert not is_newer_version("1.1.0", "1.1.2")

    def test_manifest_url_for_tag(self) -> None:
        assert manifest_url_for_tag("1.2.0").endswith("/download/v1.2.0/update-manifest.json")
        assert manifest_url_for_tag("v1.2.0").endswith("/download/v1.2.0/update-manifest.json")

    def test_can_apply_in_app_update(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import src.updater as updater_module

        install_root = tmp_path / "yt-dlp-gui"
        (install_root / "runtime").mkdir(parents=True)
        (install_root / "app").mkdir()
        (install_root / "manifest.json").write_text("{}", encoding="utf-8")

        monkeypatch.setattr(updater_module.sys, "platform", "win32")
        monkeypatch.setattr(updater_module.sys, "frozen", True, raising=False)
        monkeypatch.setattr(updater_module, "resolve_install_root", lambda: install_root)
        assert can_apply_in_app_update() is True

        monkeypatch.setattr(updater_module.sys, "platform", "darwin")
        assert can_apply_in_app_update() is False

    def test_finalize_pending_manifest(self, tmp_path: Path) -> None:
        install_root = tmp_path / "install"
        install_root.mkdir()
        pending = install_root / "manifest.json.pending"
        pending.write_text('{"app_version": "2.0.0"}\n', encoding="utf-8")
        finalize_pending_manifest(install_root)
        assert (install_root / "manifest.json").read_text(encoding="utf-8").startswith("{")
        assert not pending.exists()
