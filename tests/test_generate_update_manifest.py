"""Tests for update manifest generation helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "generate_update_manifest",
    ROOT / "scripts" / "generate_update_manifest.py",
)
assert _SPEC and _SPEC.loader
_MANIFEST = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MANIFEST
_SPEC.loader.exec_module(_MANIFEST)


class TestGenerateUpdateManifest:
    def test_select_windows_wheel_abi3_fallback(self) -> None:
        urls = [
            {
                "packagetype": "bdist_wheel",
                "filename": "pyside6-6.11.1-cp310-abi3-win_amd64.whl",
                "url": "https://example.test/wheel.whl",
                "digests": {"sha256": "abc"},
                "size": 1,
            }
        ]
        selected = _MANIFEST.select_windows_wheel(urls, python_tag="cp312")
        assert selected["filename"].endswith("win_amd64.whl")

    def test_build_manifest_includes_wheels(self) -> None:
        wheel = _MANIFEST.WheelAsset(
            package="PySide6",
            filename="pyside6.whl",
            url="https://example.test/pyside6.whl",
            sha256="abc",
            size=10,
        )
        manifest = _MANIFEST.build_manifest(
            app_version="1.2.0",
            pyside6_version="6.11.1",
            pyside6_wheels=[wheel],
            app=None,
        )
        assert manifest["app_version"] == "1.2.0"
        assert len(manifest["windows"]["pyside6_wheels"]) == 1
