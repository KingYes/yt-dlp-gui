import os
import stat
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from setup_wizard import (
    _extract_btbn_archive,
    _extract_evermeet_zip,
    _verify_ffmpeg,
    get_download_urls,
)
from utils import check_ffmpeg, get_bin_dir, get_ffmpeg_location


# ──────────────────────── get_download_urls ────────────────────────


class TestGetDownloadUrls:
    @patch("setup_wizard.platform.system", return_value="Windows")
    @patch("setup_wizard.platform.machine", return_value="AMD64")
    def test_windows_amd64(self, _m, _s) -> None:
        urls = get_download_urls()
        assert len(urls) == 1
        assert "win64" in urls[0]
        assert urls[0].endswith(".zip")

    @patch("setup_wizard.platform.system", return_value="Linux")
    @patch("setup_wizard.platform.machine", return_value="x86_64")
    def test_linux_x86_64(self, _m, _s) -> None:
        urls = get_download_urls()
        assert len(urls) == 1
        assert "linux64" in urls[0]
        assert urls[0].endswith(".tar.xz")

    @patch("setup_wizard.platform.system", return_value="Linux")
    @patch("setup_wizard.platform.machine", return_value="aarch64")
    def test_linux_arm64(self, _m, _s) -> None:
        urls = get_download_urls()
        assert len(urls) == 1
        assert "linuxarm64" in urls[0]

    @patch("setup_wizard.platform.system", return_value="Darwin")
    @patch("setup_wizard.platform.machine", return_value="arm64")
    def test_macos_arm64(self, _m, _s) -> None:
        urls = get_download_urls()
        assert len(urls) == 2
        assert "evermeet" in urls[0]
        assert "ffprobe" in urls[1]

    @patch("setup_wizard.platform.system", return_value="Darwin")
    @patch("setup_wizard.platform.machine", return_value="x86_64")
    def test_macos_x86(self, _m, _s) -> None:
        urls = get_download_urls()
        assert len(urls) == 2

    @patch("setup_wizard.platform.system", return_value="FreeBSD")
    @patch("setup_wizard.platform.machine", return_value="amd64")
    def test_unsupported_platform(self, _m, _s) -> None:
        urls = get_download_urls()
        assert urls == []


# ──────────────────────── check_ffmpeg ────────────────────────


class TestCheckFfmpeg:
    def test_custom_path_file(self, tmp_path: Path) -> None:
        fake = tmp_path / "ffmpeg"
        fake.write_bytes(b"fake")
        assert check_ffmpeg(str(fake)) is True

    def test_custom_path_dir(self, tmp_path: Path) -> None:
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        (tmp_path / name).write_bytes(b"fake")
        assert check_ffmpeg(str(tmp_path)) is True

    def test_custom_path_empty_dir(self, tmp_path: Path) -> None:
        result = check_ffmpeg(str(tmp_path))
        # Falls through to bin dir / system PATH check
        assert isinstance(result, bool)

    def test_empty_custom_path_falls_through(self) -> None:
        result = check_ffmpeg("")
        assert isinstance(result, bool)


# ──────────────────────── get_ffmpeg_location ────────────────────────


class TestGetFfmpegLocation:
    def test_custom_file_returns_parent(self, tmp_path: Path) -> None:
        fake = tmp_path / "ffmpeg"
        fake.write_bytes(b"fake")
        assert get_ffmpeg_location(str(fake)) == str(tmp_path)

    def test_custom_dir_returns_dir(self, tmp_path: Path) -> None:
        assert get_ffmpeg_location(str(tmp_path)) == str(tmp_path)

    def test_bin_dir_with_ffmpeg(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("utils.get_bin_dir", lambda: tmp_path)
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        (tmp_path / name).write_bytes(b"fake")
        assert get_ffmpeg_location("") == str(tmp_path)

    def test_no_ffmpeg_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("utils.get_bin_dir", lambda: tmp_path)
        monkeypatch.setattr("shutil.which", lambda _: None)
        assert get_ffmpeg_location("") is None


# ──────────────────────── get_bin_dir ────────────────────────


class TestGetBinDir:
    def test_returns_path(self) -> None:
        result = get_bin_dir()
        assert isinstance(result, Path)
        assert result.name == "bin"


# ──────────────────────── extraction ────────────────────────


class TestExtractBtbnArchive:
    def test_extract_zip(self, tmp_path: Path) -> None:
        archive = tmp_path / "ffmpeg.zip"
        dest = tmp_path / "bin"

        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("ffmpeg-build/bin/ffmpeg", b"#!/bin/sh\necho fake")
            zf.writestr("ffmpeg-build/bin/ffprobe", b"#!/bin/sh\necho fake")
            zf.writestr("ffmpeg-build/doc/readme.txt", b"docs")

        _extract_btbn_archive(archive, dest)

        assert (dest / "ffmpeg").exists()
        assert (dest / "ffprobe").exists()
        if sys.platform != "win32":
            assert (dest / "ffmpeg").stat().st_mode & stat.S_IXUSR

    def test_extract_zip_windows_names(self, tmp_path: Path) -> None:
        archive = tmp_path / "ffmpeg.zip"
        dest = tmp_path / "bin"

        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("ffmpeg-build/bin/ffmpeg.exe", b"MZ fake exe")
            zf.writestr("ffmpeg-build/bin/ffprobe.exe", b"MZ fake exe")

        _extract_btbn_archive(archive, dest)

        assert (dest / "ffmpeg.exe").exists()
        assert (dest / "ffprobe.exe").exists()


class TestExtractEvermeetZip:
    def test_extract_single_binary(self, tmp_path: Path) -> None:
        archive = tmp_path / "ffmpeg.zip"
        dest = tmp_path / "bin"

        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("ffmpeg", b"macho binary fake")

        _extract_evermeet_zip(archive, dest)

        assert (dest / "ffmpeg").exists()
        if sys.platform != "win32":
            assert (dest / "ffmpeg").stat().st_mode & stat.S_IXUSR

    def test_extract_ffprobe(self, tmp_path: Path) -> None:
        archive = tmp_path / "ffprobe.zip"
        dest = tmp_path / "bin"

        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("ffprobe", b"macho binary fake")

        _extract_evermeet_zip(archive, dest)
        assert (dest / "ffprobe").exists()


# ──────────────────────── verify ────────────────────────


class TestVerifyFfmpeg:
    def test_missing_binary(self, tmp_path: Path) -> None:
        assert _verify_ffmpeg(tmp_path) is False

    @pytest.mark.skipif(sys.platform == "win32", reason="shell script test")
    def test_working_binary(self, tmp_path: Path) -> None:
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.write_text("#!/bin/sh\necho 'ffmpeg version 6.0'")
        ffmpeg.chmod(0o755)
        assert _verify_ffmpeg(tmp_path) is True

    @pytest.mark.skipif(sys.platform == "win32", reason="shell script test")
    def test_broken_binary(self, tmp_path: Path) -> None:
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.write_text("#!/bin/sh\nexit 1")
        ffmpeg.chmod(0o755)
        assert _verify_ffmpeg(tmp_path) is False
