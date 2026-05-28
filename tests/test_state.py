import json

import pytest

import state as state_module
from state import AppState


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Redirect _STATE_DIR / _STATE_FILE to a temp directory for every test.

    Also reset the mutable default containers in _DEFAULT_STATE so that
    list objects (history, recent_folders) from a previous AppState instance
    don't bleed into the next one.
    """
    state_dir = tmp_path / "yt-dlp-gui"
    state_dir.mkdir()
    state_file = state_dir / "state.json"
    monkeypatch.setattr(state_module, "_STATE_DIR", state_dir)
    monkeypatch.setattr(state_module, "_STATE_FILE", state_file)
    monkeypatch.setitem(state_module._DEFAULT_STATE, "history", [])
    monkeypatch.setitem(state_module._DEFAULT_STATE, "recent_folders", [])


class TestLoadDefaults:
    def test_load_nonexistent_file(self) -> None:
        s = AppState()
        assert s.stats["total_downloads"] == 0
        assert s.history == []
        assert s.recent_folders == []

    def test_load_empty_file(self, tmp_path) -> None:
        state_file = state_module._STATE_FILE
        state_file.write_text("", encoding="utf-8")
        s = AppState()
        assert s.stats["total_downloads"] == 0

    def test_load_corrupt_json(self) -> None:
        state_module._STATE_FILE.write_text("{bad json", encoding="utf-8")
        s = AppState()
        assert s.stats["total_downloads"] == 0


class TestSaveAndReload:
    def test_round_trip(self) -> None:
        s = AppState()
        s.record_download(1024, is_audio=True, title="Test", url="https://x.com")
        s2 = AppState()
        assert s2.stats["total_downloads"] == 1
        assert s2.stats["total_bytes"] == 1024
        assert s2.stats["total_audio_downloads"] == 1
        assert len(s2.history) == 1
        assert s2.history[0]["title"] == "Test"

    def test_save_creates_file(self) -> None:
        state_module._STATE_FILE.unlink(missing_ok=True)
        s = AppState()
        s.save()
        assert state_module._STATE_FILE.exists()
        data = json.loads(state_module._STATE_FILE.read_text(encoding="utf-8"))
        assert "stats" in data


class TestRecordDownload:
    def test_increments_total(self) -> None:
        s = AppState()
        s.record_download(100)
        s.record_download(200)
        assert s.stats["total_downloads"] == 2
        assert s.stats["total_bytes"] == 300

    def test_audio_flag(self) -> None:
        s = AppState()
        s.record_download(50, is_audio=True)
        assert s.stats["total_audio_downloads"] == 1

    def test_playlist_flag(self) -> None:
        s = AppState()
        s.record_download(50, is_playlist=True)
        assert s.stats["total_playlist_downloads"] == 1

    def test_appends_history_entry_with_ok_status(self) -> None:
        s = AppState()
        s.record_download(1024, title="Song", url="https://yt.com/1")
        assert len(s.history) == 1
        assert s.history[0]["status"] == "ok"
        assert s.history[0]["bytes"] == 1024


class TestRecordFailed:
    def test_appends_error_entry(self) -> None:
        s = AppState()
        s.record_failed(title="Bad Video", url="https://yt.com/bad")
        assert len(s.history) == 1
        assert s.history[0]["status"] == "error"
        assert s.history[0]["bytes"] == 0


class TestAddRecentFolder:
    def test_adds_folder(self) -> None:
        s = AppState()
        s.add_recent_folder("/home/user/videos")
        assert s.recent_folders == ["/home/user/videos"]

    def test_deduplication_and_mru(self) -> None:
        s = AppState()
        s.add_recent_folder("/a")
        s.add_recent_folder("/b")
        s.add_recent_folder("/a")
        assert s.recent_folders == ["/a", "/b"]

    def test_max_five_folders(self) -> None:
        s = AppState()
        for i in range(7):
            s.add_recent_folder(f"/folder{i}")
        assert len(s.recent_folders) == 5
        assert s.recent_folders[0] == "/folder6"

    def test_mru_ordering(self) -> None:
        s = AppState()
        s.add_recent_folder("/old")
        s.add_recent_folder("/mid")
        s.add_recent_folder("/new")
        assert s.recent_folders[0] == "/new"


class TestSaveLastInput:
    def test_save_and_read(self) -> None:
        s = AppState()
        s.save_last_input(
            urls=["https://yt.com/1"],
            output_dir="/tmp/out",
            format_key="720p",
            split_chapters=True,
        )
        s2 = AppState()
        li = s2.last_input
        assert li["urls"] == ["https://yt.com/1"]
        assert li["output_dir"] == "/tmp/out"
        assert li["format"] == "720p"
        assert li["split_chapters"] is True

    def test_input_mode_defaults_to_single(self) -> None:
        s = AppState()
        assert s.last_input["input_mode"] == "single"

    def test_progress_view_defaults_to_simple(self) -> None:
        s = AppState()
        assert s.last_input["progress_view"] == "simple"

    def test_save_input_mode_and_progress_view(self) -> None:
        s = AppState()
        s.save_last_input(
            urls=["https://yt.com/1", "https://yt.com/2"],
            output_dir="/tmp/out",
            format_key="720p",
            split_chapters=False,
            input_mode="multiple",
            progress_view="detailed",
        )
        s2 = AppState()
        li = s2.last_input
        assert li["input_mode"] == "multiple"
        assert li["progress_view"] == "detailed"

    def test_save_last_input_preserves_defaults_when_not_provided(self) -> None:
        s = AppState()
        s.save_last_input(
            urls=["https://yt.com/1"],
            output_dir="/tmp/out",
            format_key="Best (video+audio)",
            split_chapters=False,
        )
        s2 = AppState()
        li = s2.last_input
        assert li["input_mode"] == "single"
        assert li["progress_view"] == "simple"

    def test_input_mode_backfilled_on_old_state(self) -> None:
        """Existing state.json without input_mode/progress_view gets defaults."""
        state_module._STATE_FILE.write_text(
            json.dumps({
                "last_input": {
                    "urls": ["https://yt.com/1"],
                    "output_dir": "/tmp",
                    "format": "720p",
                    "split_chapters": False,
                },
            }),
            encoding="utf-8",
        )
        s = AppState()
        assert s.last_input["input_mode"] == "single"
        assert s.last_input["progress_view"] == "simple"


class TestDownloadSectionState:
    def test_download_section_defaults(self) -> None:
        s = AppState()
        assert s.last_input["download_section"] is False
        assert s.last_input["section_start"] == ""
        assert s.last_input["section_end"] == ""

    def test_save_download_section(self) -> None:
        s = AppState()
        s.save_last_input(
            urls=["https://yt.com/1"],
            output_dir="/tmp/out",
            format_key="720p",
            split_chapters=False,
            download_section=True,
            section_start="0:30",
            section_end="2:15",
        )
        s2 = AppState()
        li = s2.last_input
        assert li["download_section"] is True
        assert li["section_start"] == "0:30"
        assert li["section_end"] == "2:15"

    def test_download_section_backfilled_on_old_state(self) -> None:
        """Existing state.json without section fields gets defaults."""
        state_module._STATE_FILE.write_text(
            json.dumps({
                "last_input": {
                    "urls": ["https://yt.com/1"],
                    "output_dir": "/tmp",
                    "format": "720p",
                    "split_chapters": False,
                    "input_mode": "single",
                    "progress_view": "simple",
                },
            }),
            encoding="utf-8",
        )
        s = AppState()
        assert s.last_input["download_section"] is False
        assert s.last_input["section_start"] == ""
        assert s.last_input["section_end"] == ""


class TestHistoryCapping:
    def test_caps_at_100(self) -> None:
        s = AppState()
        for i in range(110):
            s.record_download(1, title=f"dl-{i}", url=f"https://yt.com/{i}")
        assert len(s.history) == 100
        assert s.history[0]["title"] == "dl-10"
        assert s.history[-1]["title"] == "dl-109"
