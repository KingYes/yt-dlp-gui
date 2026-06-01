"""Download and extract official PySide6 PyPI wheels into a runtime directory."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .install_layout import app_current_dir, default_install_root, runtime_dir

ProgressCallback = Callable[[str, int, int], None]
_WHEEL_SUFFIX = ".whl"


def runtime_is_ready(path: Path) -> bool:
    return (path / "PySide6").is_dir() and (path / "shiboken6").is_dir()


def load_manifest(source: str | Path) -> dict[str, Any]:
    if isinstance(source, Path):
        return json.loads(source.read_text(encoding="utf-8"))

    text = source.strip()
    if text.startswith("{"):
        return json.loads(text)

    if text.startswith(("http://", "https://")):
        with urllib.request.urlopen(text, timeout=30) as resp:
            return json.load(resp)

    return json.loads(Path(text).read_text(encoding="utf-8"))


def _noop_progress(phase: str, current: int, total: int) -> None:
    del phase, current, total


def _download_file(url: str, dest: Path, expected_sha256: str, progress: ProgressCallback) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    tmp_path = dest.with_suffix(dest.suffix + ".part")

    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with tmp_path.open("wb") as handle:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    progress("download", downloaded, total)

        if digest.hexdigest().lower() != expected_sha256.lower():
            msg = f"SHA-256 mismatch for {dest.name}"
            raise ValueError(msg)

        tmp_path.replace(dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def extract_wheel(archive_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.namelist():
            if ".dist-info/" in member:
                continue
            zf.extract(member, dest_dir)


def extract_app_archive(archive_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.namelist()
            root_prefix = _common_zip_root(members)
            for member in members:
                if member.endswith("/"):
                    continue
                rel = member.removeprefix(root_prefix) if root_prefix else member
                if not rel:
                    continue
                target = dest_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        return

    msg = f"Unsupported app archive: {archive_path.name}"
    raise ValueError(msg)


def _common_zip_root(members: list[str]) -> str:
    dirs = {m for m in members if m.endswith("/")}
    if not dirs:
        return ""
    root = min(dirs, key=len)
    if all(m.startswith(root) for m in members if m):
        return root
    return ""


def install_pyside6_wheels(
    wheels: list[dict[str, Any]],
    dest_runtime: Path,
    *,
    progress: ProgressCallback | None = None,
) -> None:
    report = progress or _noop_progress
    total = len(wheels)
    with tempfile.TemporaryDirectory(prefix="yt-dlp-gui-wheels-") as tmp:
        tmp_dir = Path(tmp)
        for index, wheel in enumerate(wheels, start=1):
            filename = wheel["filename"]
            report("wheel", index, total)
            archive = tmp_dir / filename
            _download_file(wheel["url"], archive, wheel["sha256"], report)
            extract_wheel(archive, dest_runtime)


def install_app_bundle(
    app_info: dict[str, Any],
    dest_dir: Path,
    *,
    progress: ProgressCallback | None = None,
) -> None:
    report = progress or _noop_progress
    with tempfile.TemporaryDirectory(prefix="yt-dlp-gui-app-") as tmp:
        archive = Path(tmp) / "app.zip"
        _download_file(app_info["url"], archive, app_info["sha256"], report)
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        extract_app_archive(archive, dest_dir)


def install_from_manifest(
    manifest: dict[str, Any],
    install_root: Path,
    *,
    install_runtime: bool = True,
    install_app: bool = True,
    progress: ProgressCallback | None = None,
) -> None:
    windows = manifest.get("windows")
    if not isinstance(windows, dict):
        msg = "Manifest is missing windows section"
        raise ValueError(msg)

    install_root.mkdir(parents=True, exist_ok=True)

    if install_runtime:
        wheels = windows.get("pyside6_wheels")
        if not isinstance(wheels, list) or not wheels:
            msg = "Manifest is missing windows.pyside6_wheels"
            raise ValueError(msg)
        install_pyside6_wheels(wheels, runtime_dir(install_root), progress=progress)

    if install_app:
        app_info = windows.get("app")
        if not isinstance(app_info, dict):
            msg = "Manifest is missing windows.app"
            raise ValueError(msg)
        install_app_bundle(app_info, app_current_dir(install_root), progress=progress)

    local_manifest = install_root / "manifest.json"
    local_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_default_manifest_stub(install_root: Path, manifest: dict[str, Any]) -> None:
    install_root.mkdir(parents=True, exist_ok=True)
    (install_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def ensure_runtime(install_root: Path | None = None) -> Path:
    root = install_root or resolve_install_root_for_cli()
    runtime = runtime_dir(root)
    if runtime_is_ready(runtime):
        return runtime
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        msg = f"Runtime missing and no manifest found at {manifest_path}"
        raise FileNotFoundError(msg)
    manifest = load_manifest(manifest_path)
    install_from_manifest(manifest, root, install_runtime=True, install_app=False)
    if not runtime_is_ready(runtime):
        msg = f"PySide6 runtime is still incomplete under {runtime}"
        raise RuntimeError(msg)
    return runtime


def resolve_install_root_for_cli() -> Path:
    from .install_layout import resolve_install_root

    root = resolve_install_root()
    if root is not None:
        return root
    if sys.platform == "win32":
        return default_install_root()
    msg = "Install root could not be determined"
    raise FileNotFoundError(msg)
