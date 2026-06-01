"""Tests for install layout and PySide6 runtime helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from src.install_layout import app_current_dir, resolve_install_root, runtime_dir
from src.pyside6_installer import extract_wheel, load_manifest, runtime_is_ready
from src.runtime_paths import configure_split_runtime, find_runtime_dir


class TestInstallLayout:
    def test_resolve_install_root(self, tmp_path: Path) -> None:
        install_root = tmp_path / "yt-dlp-gui"
        (install_root / "runtime").mkdir(parents=True)
        (install_root / "app").mkdir()
        (install_root / "manifest.json").write_text("{}", encoding="utf-8")

        assert resolve_install_root(install_root / "launcher.exe") == install_root
        assert runtime_dir(install_root) == install_root / "runtime"
        assert app_current_dir(install_root) == install_root / "app" / "current"


class TestPySide6Installer:
    def test_load_manifest_from_dict(self) -> None:
        data = load_manifest('{"app_version": "1.0.0"}')
        assert data["app_version"] == "1.0.0"

    def test_extract_wheel(self, tmp_path: Path) -> None:
        wheel = tmp_path / "sample.whl"
        runtime = tmp_path / "runtime"
        with zipfile.ZipFile(wheel, "w") as zf:
            zf.writestr("PySide6/__init__.py", "")
            zf.writestr("PySide6-6.0.0.dist-info/METADATA", "")
            zf.writestr("shiboken6/__init__.py", "")

        extract_wheel(wheel, runtime)
        assert runtime_is_ready(runtime)


class TestRuntimePaths:
    def test_find_runtime_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runtime = tmp_path / "runtime"
        (runtime / "PySide6").mkdir(parents=True)
        (runtime / "shiboken6").mkdir()
        monkeypatch.setenv("YT_DLP_GUI_RUNTIME", str(runtime))
        assert find_runtime_dir() == runtime

    def test_configure_split_runtime_adds_sys_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runtime = tmp_path / "runtime"
        (runtime / "PySide6").mkdir(parents=True)
        (runtime / "shiboken6").mkdir()
        monkeypatch.setenv("YT_DLP_GUI_RUNTIME", str(runtime))
        monkeypatch.setattr("src.runtime_paths.find_runtime_dir", lambda: runtime)

        configured = configure_split_runtime()
        assert configured == runtime
        assert str(runtime) in __import__("sys").path
