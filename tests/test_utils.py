import pytest

from src.utils import (
    build_download_section_range,
    classify_url,
    format_bytes,
    format_eta,
    format_speed,
    format_timestamp,
    is_valid_url,
    parse_timestamp,
    truncate_filename,
    validate_time_range,
)

# ────────────────────────────── is_valid_url ──────────────────────────────


class TestIsValidUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com",
            "https://example.com",
            "https://example.com/path/to/page",
            "https://example.com/path?q=search&page=2",
            "https://www.youtube.com/watch?v=abc123",
            "http://localhost:8080",
            "http://192.168.1.1:3000/test",
            "https://sub.domain.example.co.uk/foo",
        ],
    )
    def test_valid_urls(self, url: str) -> None:
        assert is_valid_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not-a-url",
            "example.com",
            "ftp://files.example.com/data",
            "://missing-scheme.com",
            "just some random text",
            "   ",
        ],
    )
    def test_invalid_urls(self, url: str) -> None:
        assert is_valid_url(url) is False

    def test_strips_whitespace(self) -> None:
        assert is_valid_url("  https://example.com  ") is True


# ────────────────────────────── classify_url ──────────────────────────────


class TestClassifyUrl:
    def test_plain_video(self) -> None:
        assert classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "video"

    def test_shorts_video(self) -> None:
        assert classify_url("https://www.youtube.com/shorts/abcdef") == "video"

    def test_playlist_with_list_param_only(self) -> None:
        assert (
            classify_url("https://www.youtube.com/playlist?list=PLxxxxxx")
            == "playlist"
        )

    def test_playlist_list_param_no_video(self) -> None:
        assert (
            classify_url("https://www.youtube.com/?list=PLxxxxxx") == "playlist"
        )

    def test_ambiguous_video_and_list(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxxxxx"
        assert classify_url(url) == "ambiguous"

    def test_channel_path(self) -> None:
        assert classify_url("https://www.youtube.com/c/SomeChannel") == "playlist"

    def test_channel_full_path(self) -> None:
        assert (
            classify_url("https://www.youtube.com/channel/UCxxxxxx") == "playlist"
        )

    def test_user_playlists_path(self) -> None:
        assert (
            classify_url("https://www.youtube.com/@user/playlists") == "playlist"
        )

    def test_generic_url_defaults_to_video(self) -> None:
        assert classify_url("https://vimeo.com/123456") == "video"

    def test_strips_whitespace(self) -> None:
        assert (
            classify_url("  https://www.youtube.com/watch?v=abc  ") == "video"
        )


# ────────────────────────────── format_bytes ──────────────────────────────


class TestFormatBytes:
    def test_zero(self) -> None:
        assert format_bytes(0) == "0 B"

    def test_none(self) -> None:
        assert format_bytes(None) == "0 B"

    def test_small_bytes(self) -> None:
        assert format_bytes(512) == "512.0 B"

    def test_kilobytes(self) -> None:
        assert format_bytes(1536) == "1.5 KB"

    def test_megabytes(self) -> None:
        result = format_bytes(10 * 1024 * 1024)
        assert result == "10.0 MB"

    def test_gigabytes(self) -> None:
        result = format_bytes(2.5 * 1024**3)
        assert result == "2.5 GB"

    def test_terabytes(self) -> None:
        result = format_bytes(1024**4)
        assert result == "1.0 TB"

    def test_petabytes(self) -> None:
        result = format_bytes(1024**5)
        assert result == "1.0 PB"


# ────────────────────────────── format_speed ──────────────────────────────


class TestFormatSpeed:
    def test_none(self) -> None:
        assert format_speed(None) == "-- B/s"

    def test_zero(self) -> None:
        assert format_speed(0) == "-- B/s"

    def test_bytes_per_second(self) -> None:
        assert format_speed(500) == "500.0 B/s"

    def test_megabytes_per_second(self) -> None:
        assert format_speed(5 * 1024 * 1024) == "5.0 MB/s"


# ──────────────────────────────── format_eta ──────────────────────────────


class TestFormatEta:
    def test_none(self) -> None:
        assert format_eta(None) == "--:--"

    def test_negative(self) -> None:
        assert format_eta(-5) == "--:--"

    def test_zero(self) -> None:
        assert format_eta(0) == "--:--"

    def test_seconds_only(self) -> None:
        assert format_eta(45) == "00:45"

    def test_minutes_and_seconds(self) -> None:
        assert format_eta(125) == "02:05"

    def test_hours(self) -> None:
        assert format_eta(3661) == "1:01:01"


# ─────────────────────────── truncate_filename ────────────────────────────


class TestTruncateFilename:
    def test_short_name(self) -> None:
        assert truncate_filename("short.mp4") == "short.mp4"

    def test_exact_length(self) -> None:
        name = "x" * 50
        assert truncate_filename(name) == name

    def test_long_name_truncated(self) -> None:
        name = "x" * 60
        result = truncate_filename(name)
        assert len(result) == 50
        assert result.endswith("...")

    def test_custom_max_len(self) -> None:
        name = "abcdefghij"
        result = truncate_filename(name, max_len=8)
        assert result == "abcde..."
        assert len(result) == 8


# ────────────────────────────── parse_timestamp ──────────────────────────────


class TestParseTimestamp:
    def test_empty_string(self) -> None:
        assert parse_timestamp("") is None

    def test_whitespace_only(self) -> None:
        assert parse_timestamp("   ") is None

    def test_seconds_only(self) -> None:
        assert parse_timestamp("45") == 45.0

    def test_fractional_seconds(self) -> None:
        assert parse_timestamp("12.5") == 12.5

    def test_mm_ss(self) -> None:
        assert parse_timestamp("1:30") == 90.0

    def test_hh_mm_ss(self) -> None:
        assert parse_timestamp("1:02:03") == 3723.0

    def test_hh_mm_ss_fractional(self) -> None:
        assert parse_timestamp("0:01:30.5") == 90.5

    def test_zero(self) -> None:
        assert parse_timestamp("0") == 0.0

    def test_invalid_text(self) -> None:
        assert parse_timestamp("abc") is None

    def test_too_many_colons(self) -> None:
        assert parse_timestamp("1:2:3:4") is None

    def test_negative(self) -> None:
        assert parse_timestamp("-5") is None

    def test_strips_whitespace(self) -> None:
        assert parse_timestamp("  1:30  ") == 90.0


# ────────────────────────────── format_timestamp ──────────────────────────────


class TestFormatTimestamp:
    def test_seconds_only(self) -> None:
        assert format_timestamp(45) == "0:45"

    def test_minutes_and_seconds(self) -> None:
        assert format_timestamp(90) == "1:30"

    def test_hours(self) -> None:
        assert format_timestamp(3723) == "1:02:03"

    def test_zero(self) -> None:
        assert format_timestamp(0) == "0:00"


# ─────────────────────────── validate_time_range ─────────────────────────────


class TestValidateTimeRange:
    def test_both_empty(self) -> None:
        assert validate_time_range("", "") is not None

    def test_start_only(self) -> None:
        assert validate_time_range("1:00", "") is None

    def test_end_only(self) -> None:
        assert validate_time_range("", "2:00") is None

    def test_valid_range(self) -> None:
        assert validate_time_range("0:30", "1:30") is None

    def test_start_after_end(self) -> None:
        err = validate_time_range("2:00", "1:00")
        assert err is not None
        assert "before" in err.lower()

    def test_start_equals_end(self) -> None:
        err = validate_time_range("1:00", "1:00")
        assert err is not None

    def test_start_exceeds_duration(self) -> None:
        err = validate_time_range("5:00", "", duration=120.0)
        assert err is not None
        assert "duration" in err.lower()

    def test_end_exceeds_duration(self) -> None:
        err = validate_time_range("", "5:00", duration=120.0)
        assert err is not None

    def test_valid_within_duration(self) -> None:
        assert validate_time_range("0:30", "1:30", duration=120.0) is None


# ────────────────────── build_download_section_range ─────────────────────────


class TestBuildDownloadSectionRange:
    def test_both_empty(self) -> None:
        assert build_download_section_range("", "") is None

    def test_start_only(self) -> None:
        result = build_download_section_range("1:30", "")
        assert result == (90.0, float("inf"))

    def test_end_only(self) -> None:
        result = build_download_section_range("", "2:00")
        assert result == (0.0, 120.0)

    def test_both_values(self) -> None:
        result = build_download_section_range("0:30", "1:45")
        assert result == (30.0, 105.0)
