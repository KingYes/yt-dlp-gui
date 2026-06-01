"""Generate update-manifest.json with pinned PySide6 PyPI wheels for Windows."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_PYPI_JSON = "https://pypi.org/pypi/{package}/{version}/json"
_PYSIDE6_RUNTIME_PACKAGES = (
    "PySide6",
    "shiboken6",
    "PySide6_Essentials",
    "PySide6_Addons",
)


@dataclass(frozen=True)
class WheelAsset:
    package: str
    filename: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class AppAsset:
    url: str
    sha256: str
    size: int


def read_project_version(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        msg = f"Could not read version from {pyproject_path}"
        raise ValueError(msg)
    return match.group(1)


def read_pyside6_requirement(requirements_path: Path) -> str:
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("pyside6"):
            return stripped.split("#", 1)[0].strip()
    msg = f"PySide6 requirement not found in {requirements_path}"
    raise ValueError(msg)


def resolve_pyside6_version(*, requirement: str, override: str | None) -> str:
    if override:
        return override
    try:
        return importlib.metadata.version("PySide6")
    except importlib.metadata.PackageNotFoundError:
        pass

    exact = re.match(r"^PySide6==(.+)$", requirement, re.IGNORECASE)
    if exact:
        return exact.group(1).strip()

    minimum = re.match(r"^PySide6>=(.+)$", requirement, re.IGNORECASE)
    if minimum:
        return _latest_pypi_version("PySide6", minimum=minimum.group(1).strip())

    msg = f"Unsupported PySide6 requirement: {requirement!r}. Install PySide6 or pass --pyside6-version."
    raise ValueError(msg)


def _latest_pypi_version(package: str, *, minimum: str) -> str:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=30) as resp:
        data = json.load(resp)
    versions = [v for v in data.get("releases", {}) if _version_at_least(v, minimum)]
    if not versions:
        msg = f"No {package} release found matching >={minimum}"
        raise ValueError(msg)
    best: str = max(versions, key=_parse_version_tuple)
    return best


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _version_at_least(version: str, minimum: str) -> bool:
    return _parse_version_tuple(version) >= _parse_version_tuple(minimum)


def fetch_pypi_release(package: str, version: str) -> dict[str, Any]:
    url = _PYPI_JSON.format(package=package, version=version)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data: dict[str, Any] = json.load(resp)
            return data
    except urllib.error.HTTPError as exc:
        msg = f"PyPI release not found for {package} {version}: {exc.code}"
        raise ValueError(msg) from exc


def select_windows_wheel(urls: list[dict[str, Any]], *, python_tag: str) -> dict[str, Any]:
    wheels = [entry for entry in urls if entry.get("packagetype") == "bdist_wheel" and "win_amd64" in entry.get("filename", "")]
    if not wheels:
        msg = "No win_amd64 wheels found"
        raise ValueError(msg)

    exact = [w for w in wheels if f"-{python_tag}-" in w["filename"]]
    if exact:
        return exact[0]

    abi3 = [w for w in wheels if "abi3" in w["filename"]]
    if abi3:
        return abi3[0]

    msg = f"No wheel matching python tag {python_tag!r} or abi3 on win_amd64"
    raise ValueError(msg)


def resolve_pyside6_wheels(
    version: str,
    *,
    python_tag: str = "cp312",
) -> list[WheelAsset]:
    wheels: list[WheelAsset] = []
    for package in _PYSIDE6_RUNTIME_PACKAGES:
        release = fetch_pypi_release(package, version)
        selected = select_windows_wheel(release.get("urls", []), python_tag=python_tag)
        digests = selected.get("digests") or {}
        sha256 = digests.get("sha256")
        if not sha256:
            msg = f"Missing sha256 digest for {selected['filename']}"
            raise ValueError(msg)
        wheels.append(
            WheelAsset(
                package=package,
                filename=selected["filename"],
                url=selected["url"],
                sha256=sha256,
                size=int(selected.get("size", 0)),
            )
        )
    return wheels


def build_manifest(
    *,
    app_version: str,
    pyside6_version: str,
    pyside6_wheels: list[WheelAsset],
    app: AppAsset | None,
) -> dict[str, Any]:
    windows: dict[str, Any] = {
        "pyside6_wheels": [
            {
                "package": wheel.package,
                "filename": wheel.filename,
                "url": wheel.url,
                "sha256": wheel.sha256,
                "size": wheel.size,
            }
            for wheel in pyside6_wheels
        ],
    }
    if app is not None:
        windows["app"] = {
            "url": app.url,
            "sha256": app.sha256,
            "size": app.size,
        }

    return {
        "app_version": app_version,
        "pyside6_version": pyside6_version,
        "windows": windows,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=_ROOT / "update-manifest.json")
    parser.add_argument("--pyproject", type=Path, default=_ROOT / "pyproject.toml")
    parser.add_argument("--requirements", type=Path, default=_ROOT / "requirements.txt")
    parser.add_argument("--app-version", help="Defaults to pyproject.toml version")
    parser.add_argument("--pyside6-version", help="Defaults to installed PySide6 or requirements.txt")
    parser.add_argument("--python-tag", default="cp312", help="PyInstaller embedded Python tag")
    parser.add_argument("--app-url")
    parser.add_argument("--app-sha256")
    parser.add_argument("--app-size", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    app_version = args.app_version or read_project_version(args.pyproject)
    requirement = read_pyside6_requirement(args.requirements)
    pyside6_version = resolve_pyside6_version(requirement=requirement, override=args.pyside6_version)
    pyside6_wheels = resolve_pyside6_wheels(pyside6_version, python_tag=args.python_tag)

    app: AppAsset | None = None
    app_fields = (args.app_url, args.app_sha256, args.app_size)
    if any(app_fields):
        if not all(app_fields):
            print("Error: --app-url, --app-sha256, and --app-size must be provided together", file=sys.stderr)
            return 1
        app = AppAsset(url=args.app_url, sha256=args.app_sha256, size=args.app_size)

    manifest = build_manifest(
        app_version=app_version,
        pyside6_version=pyside6_version,
        pyside6_wheels=pyside6_wheels,
        app=app,
    )

    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} (app {app_version}, PySide6 {pyside6_version}, {len(pyside6_wheels)} wheels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
