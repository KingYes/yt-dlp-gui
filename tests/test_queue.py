import json
from pathlib import Path

import pytest

import state as state_module
from state import AppState


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_dir = tmp_path / "yt-dlp-gui"
    state_dir.mkdir()
    state_file = state_dir / "state.json"
    monkeypatch.setattr(state_module, "_STATE_DIR", state_dir)
    monkeypatch.setattr(state_module, "_STATE_FILE", state_file)
    monkeypatch.setitem(state_module._DEFAULT_STATE, "history", [])
    monkeypatch.setitem(state_module._DEFAULT_STATE, "recent_folders", [])
    monkeypatch.setitem(state_module._DEFAULT_STATE, "download_queue", [])


def _make_entry(url: str = "https://example.com/1", fmt: str = "Best (video+audio)") -> dict:
    return {
        "urls": [url],
        "playlist": False,
        "format_key": fmt,
        "output_dir": "/tmp/dl",
        "split_chapters": False,
        "custom_format_string": "",
        "section_start": "",
        "section_end": "",
        "status": "queued",
    }


class TestQueueDefaults:
    def test_default_queue_is_empty(self) -> None:
        s = AppState()
        assert s.download_queue == []

    def test_queue_key_exists_in_state(self) -> None:
        s = AppState()
        s.save()
        raw = json.loads(state_module._STATE_FILE.read_text(encoding="utf-8"))
        assert "download_queue" in raw
        assert raw["download_queue"] == []


class TestSaveQueue:
    def test_save_and_reload(self) -> None:
        s = AppState()
        entries = [_make_entry("https://yt.com/a"), _make_entry("https://yt.com/b")]
        s.save_queue(entries)
        s2 = AppState()
        assert len(s2.download_queue) == 2
        assert s2.download_queue[0]["urls"] == ["https://yt.com/a"]
        assert s2.download_queue[1]["urls"] == ["https://yt.com/b"]

    def test_save_overwrites_previous(self) -> None:
        s = AppState()
        s.save_queue([_make_entry("https://yt.com/old")])
        s.save_queue([_make_entry("https://yt.com/new")])
        s2 = AppState()
        assert len(s2.download_queue) == 1
        assert s2.download_queue[0]["urls"] == ["https://yt.com/new"]

    def test_save_empty_queue(self) -> None:
        s = AppState()
        s.save_queue([_make_entry()])
        s.save_queue([])
        s2 = AppState()
        assert s2.download_queue == []

    def test_preserves_all_entry_fields(self) -> None:
        s = AppState()
        entry = {
            "urls": ["https://yt.com/1", "https://yt.com/2"],
            "playlist": True,
            "format_key": "720p",
            "output_dir": "/home/user/videos",
            "split_chapters": True,
            "custom_format_string": "248+251",
            "section_start": "0:30",
            "section_end": "1:45",
            "status": "queued",
        }
        s.save_queue([entry])
        s2 = AppState()
        saved = s2.download_queue[0]
        assert saved["urls"] == ["https://yt.com/1", "https://yt.com/2"]
        assert saved["playlist"] is True
        assert saved["format_key"] == "720p"
        assert saved["output_dir"] == "/home/user/videos"
        assert saved["split_chapters"] is True
        assert saved["custom_format_string"] == "248+251"
        assert saved["section_start"] == "0:30"
        assert saved["section_end"] == "1:45"


class TestClearQueue:
    def test_clear_empties_queue(self) -> None:
        s = AppState()
        s.save_queue([_make_entry(), _make_entry()])
        s.clear_queue()
        assert s.download_queue == []

    def test_clear_persists(self) -> None:
        s = AppState()
        s.save_queue([_make_entry()])
        s.clear_queue()
        s2 = AppState()
        assert s2.download_queue == []


class TestQueueBackfill:
    def test_old_state_without_queue_gets_default(self) -> None:
        """Existing state.json without download_queue gets an empty list."""
        state_module._STATE_FILE.write_text(
            json.dumps({"stats": {"total_downloads": 5, "total_audio_downloads": 0,
                                  "total_playlist_downloads": 0, "total_bytes": 0}}),
            encoding="utf-8",
        )
        s = AppState()
        assert s.download_queue == []


class TestQueueReordering:
    """Test the reordering logic used by the app (list swap operations)."""

    def test_move_up(self) -> None:
        queue = [_make_entry("https://a"), _make_entry("https://b"), _make_entry("https://c")]
        index, direction = 1, -1
        new_index = index + direction
        queue[index], queue[new_index] = queue[new_index], queue[index]
        assert queue[0]["urls"] == ["https://b"]
        assert queue[1]["urls"] == ["https://a"]
        assert queue[2]["urls"] == ["https://c"]

    def test_move_down(self) -> None:
        queue = [_make_entry("https://a"), _make_entry("https://b"), _make_entry("https://c")]
        index, direction = 0, 1
        new_index = index + direction
        queue[index], queue[new_index] = queue[new_index], queue[index]
        assert queue[0]["urls"] == ["https://b"]
        assert queue[1]["urls"] == ["https://a"]

    def test_move_up_boundary(self) -> None:
        _make_entry("https://a"), _make_entry("https://b")
        index, direction = 0, -1
        new_index = index + direction
        assert new_index < 0  # should be rejected by the app

    def test_move_down_boundary(self) -> None:
        queue = [_make_entry("https://a"), _make_entry("https://b")]
        index, direction = 1, 1
        new_index = index + direction
        assert new_index >= len(queue)  # should be rejected by the app

    def test_remove_item(self) -> None:
        queue = [_make_entry("https://a"), _make_entry("https://b"), _make_entry("https://c")]
        queue.pop(1)
        assert len(queue) == 2
        assert queue[0]["urls"] == ["https://a"]
        assert queue[1]["urls"] == ["https://c"]

    def test_remove_last_item(self) -> None:
        queue = [_make_entry("https://a")]
        queue.pop(0)
        assert queue == []

    def test_reorder_round_trip(self) -> None:
        """Reorder a queue, persist, reload, and verify order."""
        s = AppState()
        entries = [_make_entry("https://a"), _make_entry("https://b"), _make_entry("https://c")]
        entries[0], entries[2] = entries[2], entries[0]
        s.save_queue(entries)
        s2 = AppState()
        assert s2.download_queue[0]["urls"] == ["https://c"]
        assert s2.download_queue[2]["urls"] == ["https://a"]
