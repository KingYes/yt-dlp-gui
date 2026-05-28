from pathlib import Path

from src.download_manager import (
    DownloadManager,
    build_format_string,
    parse_chapters,
    parse_formats,
    parse_subtitles,
)


def _noop_progress(d: dict) -> None:
    pass


def _build(
    format_key: str = "Best (video+audio)",
    output_dir: str = "/tmp/dl",
    split_chapters: bool = False,
    playlist: bool = False,
    section_start: str = "",
    section_end: str = "",
    format_string: str = "",
    settings: dict | None = None,
    selected_chapters: list[str] | None = None,
    selected_subtitle_langs: list[str] | None = None,
) -> dict:
    dm = DownloadManager()
    return dm._build_opts(
        format_key=format_key,
        output_dir=output_dir,
        progress_callback=_noop_progress,
        split_chapters=split_chapters,
        playlist=playlist,
        section_start=section_start,
        section_end=section_end,
        format_string=format_string,
        settings=settings,
        selected_chapters=selected_chapters,
        selected_subtitle_langs=selected_subtitle_langs,
    )


class TestDefaultFormat:
    def test_format_string(self) -> None:
        opts = _build()
        assert opts["format"] == (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        )

    def test_default_outtmpl(self) -> None:
        opts = _build(output_dir="/videos")
        expected = str(Path("/videos") / "%(title)s.%(ext)s")
        assert opts["outtmpl"] == expected

    def test_noplaylist_true(self) -> None:
        opts = _build()
        assert opts["noplaylist"] is True

    def test_unknown_format_falls_back_to_best(self) -> None:
        opts = _build(format_key="nonexistent preset")
        assert opts["format"] == "best"


class TestAudioOnly:
    def test_has_extract_audio_postprocessor(self) -> None:
        opts = _build(format_key="Audio Only (mp3)")
        pps = opts.get("postprocessors", [])
        keys = [pp["key"] for pp in pps]
        assert "FFmpegExtractAudio" in keys

    def test_extract_audio_config(self) -> None:
        opts = _build(format_key="Audio Only (mp3)")
        pp = next(p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio")
        assert pp["preferredcodec"] == "mp3"
        assert pp["preferredquality"] == "192"

    def test_audio_format_string(self) -> None:
        opts = _build(format_key="Audio Only (mp3)")
        assert opts["format"] == "bestaudio/best"


class TestSplitChapters:
    def test_has_split_chapters_postprocessor(self) -> None:
        opts = _build(split_chapters=True)
        pps = opts.get("postprocessors", [])
        keys = [pp["key"] for pp in pps]
        assert "FFmpegSplitChapters" in keys

    def test_outtmpl_contains_section_title(self) -> None:
        opts = _build(split_chapters=True, output_dir="/out")
        expected = str(
            Path("/out") / "%(title)s - %(section_title)s.%(ext)s"
        )
        assert opts["outtmpl"] == expected

    def test_audio_and_split_chapters_combined(self) -> None:
        opts = _build(format_key="Audio Only (mp3)", split_chapters=True)
        keys = [pp["key"] for pp in opts["postprocessors"]]
        assert "FFmpegExtractAudio" in keys
        assert "FFmpegSplitChapters" in keys


class TestPlaylistMode:
    def test_noplaylist_false(self) -> None:
        opts = _build(playlist=True)
        assert opts["noplaylist"] is False

    def test_outtmpl_has_playlist_subfolder(self) -> None:
        opts = _build(playlist=True, output_dir="/dl")
        expected = str(
            Path("/dl") / "%(playlist_title,title)s" / "%(title)s.%(ext)s"
        )
        assert opts["outtmpl"] == expected


class TestNonPlaylist:
    def test_noplaylist_true(self) -> None:
        opts = _build(playlist=False)
        assert opts["noplaylist"] is True

    def test_standard_outtmpl(self) -> None:
        opts = _build(playlist=False, output_dir="/out")
        expected = str(Path("/out") / "%(title)s.%(ext)s")
        assert opts["outtmpl"] == expected


class TestDownloadSection:
    def test_no_section_by_default(self) -> None:
        opts = _build()
        assert "download_ranges" not in opts
        assert "force_keyframes_at_cuts" not in opts

    def test_empty_section_no_ranges(self) -> None:
        opts = _build(section_start="", section_end="")
        assert "download_ranges" not in opts

    def test_section_start_only(self) -> None:
        opts = _build(section_start="1:30")
        assert "download_ranges" in opts
        assert opts["force_keyframes_at_cuts"] is True

    def test_section_end_only(self) -> None:
        opts = _build(section_end="2:00")
        assert "download_ranges" in opts
        assert opts["force_keyframes_at_cuts"] is True

    def test_section_start_and_end(self) -> None:
        opts = _build(section_start="0:30", section_end="1:45")
        assert "download_ranges" in opts
        assert opts["force_keyframes_at_cuts"] is True

    def test_download_ranges_is_callable(self) -> None:
        opts = _build(section_start="0:30", section_end="1:45")
        assert callable(opts["download_ranges"])


class TestFormatStringOverride:
    def test_override_bypasses_preset(self) -> None:
        opts = _build(format_key="Best (video+audio)", format_string="248+251")
        assert opts["format"] == "248+251"

    def test_empty_override_uses_preset(self) -> None:
        opts = _build(format_key="720p", format_string="")
        assert opts["format"] == (
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
        )

    def test_override_with_audio_only_id(self) -> None:
        opts = _build(format_key="Audio Only (mp3)", format_string="251")
        assert opts["format"] == "251"


class TestBuildFormatString:
    def test_video_and_audio(self) -> None:
        assert build_format_string("248", "251") == "248+251"

    def test_video_only(self) -> None:
        assert build_format_string("248", "") == "248"

    def test_audio_only(self) -> None:
        assert build_format_string("", "251") == "251"

    def test_neither(self) -> None:
        assert build_format_string("", "") == "best"


class TestParseFormats:
    def _sample_info(self) -> dict:
        return {
            "formats": [
                {
                    "format_id": "248",
                    "ext": "webm",
                    "vcodec": "vp9",
                    "acodec": "none",
                    "height": 1080,
                    "width": 1920,
                    "filesize": 50_000_000,
                },
                {
                    "format_id": "136",
                    "ext": "mp4",
                    "vcodec": "avc1.64001f",
                    "acodec": "none",
                    "height": 720,
                    "width": 1280,
                    "filesize": 30_000_000,
                },
                {
                    "format_id": "247",
                    "ext": "webm",
                    "vcodec": "vp9",
                    "acodec": "none",
                    "height": 720,
                    "width": 1280,
                    "filesize": 25_000_000,
                },
                {
                    "format_id": "251",
                    "ext": "webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "abr": 160,
                    "filesize": 4_000_000,
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128,
                    "filesize": 3_500_000,
                },
                {
                    "format_id": "250",
                    "ext": "webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "abr": 70,
                    "filesize": 2_000_000,
                },
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "vcodec": "avc1.42001E",
                    "acodec": "mp4a.40.2",
                    "height": 360,
                    "width": 640,
                    "filesize": 15_000_000,
                },
            ]
        }

    def test_separates_video_and_audio(self) -> None:
        video, audio = parse_formats(self._sample_info())
        assert len(video) >= 2
        assert len(audio) >= 2

    def test_video_sorted_by_height_descending(self) -> None:
        video, _ = parse_formats(self._sample_info())
        heights = [v["height"] for v in video]
        assert heights == sorted(heights, reverse=True)

    def test_audio_sorted_by_bitrate_descending(self) -> None:
        _, audio = parse_formats(self._sample_info())
        bitrates = [a["abr"] for a in audio]
        assert bitrates == sorted(bitrates, reverse=True)

    def test_video_deduplicates_by_height_and_ext(self) -> None:
        video, _ = parse_formats(self._sample_info())
        keys = [(v["height"], v["ext"]) for v in video]
        assert len(keys) == len(set(keys))

    def test_audio_deduplicates_by_bitrate_and_ext(self) -> None:
        _, audio = parse_formats(self._sample_info())
        keys = [(a["abr"], a["ext"]) for a in audio]
        assert len(keys) == len(set(keys))

    def test_combined_streams_excluded(self) -> None:
        video, audio = parse_formats(self._sample_info())
        all_ids = [v["format_id"] for v in video] + [a["format_id"] for a in audio]
        assert "18" not in all_ids

    def test_video_entry_has_required_keys(self) -> None:
        video, _ = parse_formats(self._sample_info())
        entry = video[0]
        assert "format_id" in entry
        assert "ext" in entry
        assert "height" in entry
        assert "label" in entry
        assert "vcodec" in entry

    def test_audio_entry_has_required_keys(self) -> None:
        _, audio = parse_formats(self._sample_info())
        entry = audio[0]
        assert "format_id" in entry
        assert "ext" in entry
        assert "abr" in entry
        assert "label" in entry
        assert "acodec" in entry

    def test_empty_formats(self) -> None:
        video, audio = parse_formats({})
        assert video == []
        assert audio == []

    def test_no_video_streams(self) -> None:
        info = {"formats": [
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128},
        ]}
        video, audio = parse_formats(info)
        assert video == []
        assert len(audio) == 1

    def test_no_audio_streams(self) -> None:
        info = {"formats": [
            {"format_id": "248", "ext": "webm", "vcodec": "vp9", "acodec": "none", "height": 1080},
        ]}
        video, audio = parse_formats(info)
        assert len(video) == 1
        assert audio == []

    def test_keeps_largest_filesize_per_group(self) -> None:
        video, _ = parse_formats(self._sample_info())
        webm_720 = [v for v in video if v["height"] == 720 and v["ext"] == "webm"]
        assert len(webm_720) == 1
        assert webm_720[0]["format_id"] == "247" or webm_720[0]["filesize"] == 25_000_000

    def test_label_contains_resolution(self) -> None:
        video, _ = parse_formats(self._sample_info())
        labels = [v["label"] for v in video]
        assert any("1080p" in lbl for lbl in labels)
        assert any("720p" in lbl for lbl in labels)


class TestBuildBaseOpts:
    """Verify _build_base_opts produces options without progress hooks."""

    def test_no_progress_hooks(self) -> None:
        dm = DownloadManager()
        opts = dm._build_base_opts("Best (video+audio)", "/tmp")
        assert "progress_hooks" not in opts

    def test_build_opts_adds_hooks(self) -> None:
        dm = DownloadManager()
        opts = dm._build_opts("Best (video+audio)", "/tmp", lambda d: None)
        assert "progress_hooks" in opts
        assert len(opts["progress_hooks"]) == 1

    def test_base_opts_match_build_opts_content(self) -> None:
        dm = DownloadManager()
        base = dm._build_base_opts("720p", "/out", split_chapters=True)
        full = dm._build_opts("720p", "/out", lambda d: None, split_chapters=True)
        del full["progress_hooks"]
        del full["postprocessor_hooks"]
        assert base == full


class TestPostProcessingConversion:
    """Tests for the convert_format setting."""

    def test_no_conversion_by_default(self) -> None:
        opts = _build()
        pps = opts.get("postprocessors", [])
        keys = [pp["key"] for pp in pps]
        assert "FFmpegVideoConvertor" not in keys
        assert "FFmpegExtractAudio" not in keys

    def test_empty_convert_format_no_postprocessor(self) -> None:
        opts = _build(settings={"convert_format": ""})
        pps = opts.get("postprocessors", [])
        keys = [pp["key"] for pp in pps]
        assert "FFmpegVideoConvertor" not in keys

    def test_video_conversion_mp4(self) -> None:
        opts = _build(settings={"convert_format": "mp4"})
        pps = opts["postprocessors"]
        convertor = next(p for p in pps if p["key"] == "FFmpegVideoConvertor")
        assert convertor["preferedformat"] == "mp4"

    def test_video_conversion_mkv(self) -> None:
        opts = _build(settings={"convert_format": "mkv"})
        pps = opts["postprocessors"]
        convertor = next(p for p in pps if p["key"] == "FFmpegVideoConvertor")
        assert convertor["preferedformat"] == "mkv"

    def test_video_conversion_webm(self) -> None:
        opts = _build(settings={"convert_format": "webm"})
        pps = opts["postprocessors"]
        convertor = next(p for p in pps if p["key"] == "FFmpegVideoConvertor")
        assert convertor["preferedformat"] == "webm"

    def test_audio_conversion_mp3(self) -> None:
        opts = _build(settings={"convert_format": "mp3"})
        pps = opts["postprocessors"]
        extractor = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
        assert extractor["preferredcodec"] == "mp3"

    def test_audio_conversion_aac(self) -> None:
        opts = _build(settings={"convert_format": "aac"})
        pps = opts["postprocessors"]
        extractor = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
        assert extractor["preferredcodec"] == "aac"

    def test_audio_conversion_flac(self) -> None:
        opts = _build(settings={"convert_format": "flac"})
        pps = opts["postprocessors"]
        extractor = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
        assert extractor["preferredcodec"] == "flac"

    def test_audio_conversion_wav(self) -> None:
        opts = _build(settings={"convert_format": "wav"})
        pps = opts["postprocessors"]
        extractor = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
        assert extractor["preferredcodec"] == "wav"

    def test_audio_conversion_ogg(self) -> None:
        opts = _build(settings={"convert_format": "ogg"})
        pps = opts["postprocessors"]
        extractor = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
        assert extractor["preferredcodec"] == "ogg"

    def test_conversion_skipped_for_audio_only_preset(self) -> None:
        opts = _build(format_key="Audio Only (mp3)", settings={"convert_format": "mp4"})
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegVideoConvertor" not in keys
        assert keys.count("FFmpegExtractAudio") == 1

    def test_conversion_combined_with_embed_thumbnail(self) -> None:
        opts = _build(settings={"convert_format": "mkv", "embed_thumbnail": True})
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "EmbedThumbnail" in keys
        assert "FFmpegVideoConvertor" in keys

    def test_conversion_combined_with_embed_metadata(self) -> None:
        opts = _build(settings={"convert_format": "mp4", "embed_metadata": True})
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegMetadata" in keys
        assert "FFmpegVideoConvertor" in keys


class TestSubtitleSettings:
    """Tests for subtitle download/embed/burn settings."""

    def test_no_subtitles_by_default(self) -> None:
        opts = _build()
        assert opts.get("writesubtitles") is not True
        assert opts.get("writeautomaticsub") is not True

    def test_empty_subtitle_mode_no_subtitles(self) -> None:
        opts = _build(settings={"subtitle_mode": ""})
        assert opts.get("writesubtitles") is not True

    def test_embed_mode_enables_subtitle_writing(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed"})
        assert opts["writesubtitles"] is True
        assert opts["writeautomaticsub"] is True
        assert "subtitleslangs" in opts

    def test_embed_mode_adds_embed_postprocessor(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed"})
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegEmbedSubtitle" in keys

    def test_file_mode_enables_subtitle_writing(self) -> None:
        opts = _build(settings={"subtitle_mode": "file"})
        assert opts["writesubtitles"] is True
        assert opts["writeautomaticsub"] is True

    def test_file_mode_no_embed_postprocessor(self) -> None:
        opts = _build(settings={"subtitle_mode": "file"})
        pps = opts.get("postprocessors", [])
        keys = [pp["key"] for pp in pps]
        assert "FFmpegEmbedSubtitle" not in keys

    def test_subtitle_languages_default(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed"})
        assert opts["subtitleslangs"] == ["en"]

    def test_subtitle_languages_custom(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed", "subtitle_languages": "en, es, fr"})
        assert opts["subtitleslangs"] == ["en", "es", "fr"]

    def test_subtitle_languages_all(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed", "subtitle_languages": "all"})
        assert opts["subtitleslangs"] == ["all"]

    def test_subtitle_format_preference(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed"})
        assert opts["subtitlesformat"] == "srt/ass/best"

    def test_burn_subtitles_enables_embed(self) -> None:
        opts = _build(settings={"subtitle_burn": True})
        assert opts["writesubtitles"] is True
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegEmbedSubtitle" in keys

    def test_burn_and_embed_combined(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed", "subtitle_burn": True})
        assert opts["writesubtitles"] is True
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegEmbedSubtitle" in keys

    def test_subtitles_with_conversion(self) -> None:
        opts = _build(settings={
            "subtitle_mode": "embed",
            "convert_format": "mkv",
        })
        pps = opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegEmbedSubtitle" in keys
        assert "FFmpegVideoConvertor" in keys


class TestShouldBurnSubs:
    """Tests for _should_burn_subs static method."""

    def test_false_with_no_settings(self) -> None:
        assert DownloadManager._should_burn_subs(None) is False

    def test_false_with_empty_settings(self) -> None:
        assert DownloadManager._should_burn_subs({}) is False

    def test_false_without_burn_flag(self) -> None:
        assert DownloadManager._should_burn_subs({"subtitle_mode": "embed"}) is False

    def test_true_with_burn_flag(self) -> None:
        assert DownloadManager._should_burn_subs({"subtitle_burn": True}) is True

    def test_true_with_burn_and_mode(self) -> None:
        assert DownloadManager._should_burn_subs({
            "subtitle_burn": True, "subtitle_mode": "embed",
        }) is True

    def test_false_with_burn_disabled(self) -> None:
        assert DownloadManager._should_burn_subs({"subtitle_burn": False}) is False


class TestParseSubtitles:
    """Tests for parse_subtitles helper."""

    def test_empty_info(self) -> None:
        result = parse_subtitles({})
        assert result == {"manual": [], "auto": []}

    def test_manual_subtitles(self) -> None:
        info = {
            "subtitles": {
                "en": [{"ext": "srt", "name": "English"}],
                "es": [{"ext": "srt", "name": "Spanish"}],
            },
        }
        result = parse_subtitles(info)
        assert len(result["manual"]) == 2
        assert result["auto"] == []
        codes = [s["code"] for s in result["manual"]]
        assert "en" in codes
        assert "es" in codes

    def test_auto_captions(self) -> None:
        info = {
            "automatic_captions": {
                "en": [{"ext": "vtt", "name": "English"}],
                "ja": [{"ext": "vtt", "name": "Japanese"}],
            },
        }
        result = parse_subtitles(info)
        assert result["manual"] == []
        assert len(result["auto"]) == 2

    def test_both_manual_and_auto(self) -> None:
        info = {
            "subtitles": {"en": [{"ext": "srt", "name": "English"}]},
            "automatic_captions": {"fr": [{"ext": "vtt", "name": "French"}]},
        }
        result = parse_subtitles(info)
        assert len(result["manual"]) == 1
        assert len(result["auto"]) == 1
        assert result["manual"][0]["code"] == "en"
        assert result["auto"][0]["code"] == "fr"

    def test_name_fallback_to_code(self) -> None:
        info = {"subtitles": {"zh-Hans": [{"ext": "srt"}]}}
        result = parse_subtitles(info)
        assert result["manual"][0]["name"] == "zh-Hans"

    def test_sorted_by_name(self) -> None:
        info = {
            "subtitles": {
                "zh": [{"ext": "srt", "name": "Chinese"}],
                "ar": [{"ext": "srt", "name": "Arabic"}],
                "en": [{"ext": "srt", "name": "English"}],
            },
        }
        result = parse_subtitles(info)
        names = [s["name"] for s in result["manual"]]
        assert names == ["Arabic", "Chinese", "English"]


class TestParseChapters:
    """Tests for parse_chapters helper."""

    def test_empty_info(self) -> None:
        result = parse_chapters({})
        assert result == []

    def test_no_chapters_key(self) -> None:
        result = parse_chapters({"title": "Video"})
        assert result == []

    def test_basic_chapters(self) -> None:
        info = {
            "chapters": [
                {"title": "Intro", "start_time": 0, "end_time": 60},
                {"title": "Main", "start_time": 60, "end_time": 300},
                {"title": "Outro", "start_time": 300, "end_time": 360},
            ],
        }
        result = parse_chapters(info)
        assert len(result) == 3
        assert result[0]["title"] == "Intro"
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 60.0
        assert result[0]["index"] == 0
        assert result[2]["title"] == "Outro"

    def test_sorted_by_start_time(self) -> None:
        info = {
            "chapters": [
                {"title": "Second", "start_time": 60, "end_time": 120},
                {"title": "First", "start_time": 0, "end_time": 60},
            ],
        }
        result = parse_chapters(info)
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Second"

    def test_missing_title_generates_default(self) -> None:
        info = {
            "chapters": [
                {"start_time": 0, "end_time": 30},
                {"start_time": 30, "end_time": 60},
            ],
        }
        result = parse_chapters(info)
        assert result[0]["title"] == "Chapter 1"
        assert result[1]["title"] == "Chapter 2"


class TestSelectedChaptersOpts:
    """Tests for chapter selection in _build_base_opts."""

    def test_no_chapters_no_download_ranges(self) -> None:
        opts = _build()
        assert "download_ranges" not in opts

    def test_selected_chapters_sets_download_ranges(self) -> None:
        opts = _build(selected_chapters=["Intro", "Outro"])
        assert "download_ranges" in opts
        assert "force_keyframes_at_cuts" not in opts

    def test_section_takes_precedence_over_chapters(self) -> None:
        opts = _build(
            section_start="0:10", section_end="1:00",
            selected_chapters=["Intro"],
        )
        assert "download_ranges" in opts
        assert opts["force_keyframes_at_cuts"] is True


class TestSelectedSubtitleLangs:
    """Tests for selected_subtitle_langs in _build_base_opts."""

    def test_no_selection_uses_settings(self) -> None:
        opts = _build(settings={"subtitle_mode": "embed", "subtitle_languages": "es,fr"})
        assert opts["subtitleslangs"] == ["es", "fr"]

    def test_selection_overrides_settings(self) -> None:
        opts = _build(
            settings={"subtitle_mode": "embed", "subtitle_languages": "es,fr"},
            selected_subtitle_langs=["en", "ja"],
        )
        assert opts["subtitleslangs"] == ["en", "ja"]

    def test_selection_enables_subtitles_without_mode(self) -> None:
        opts = _build(selected_subtitle_langs=["en"])
        assert opts.get("writesubtitles") is True
        assert opts.get("writeautomaticsub") is True
        assert opts["subtitleslangs"] == ["en"]

    def test_no_selection_no_mode_skips_subtitles(self) -> None:
        opts = _build(settings={})
        assert "writesubtitles" not in opts
