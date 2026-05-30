_RESOLUTION_LABELS = {
    4320: "4320p (8K)",
    2160: "2160p (4K)",
    1440: "1440p (2K)",
    1080: "1080p",
    720: "720p",
    480: "480p",
    360: "360p",
    240: "240p",
    144: "144p",
}


def parse_formats(info_dict: dict) -> tuple[list[dict], list[dict]]:
    """Parse info_dict formats into grouped video and audio stream lists.

    Returns (video_formats, audio_formats). Each video entry:
        {"format_id": str, "ext": str, "height": int, "filesize": int | None,
         "vcodec": str, "label": str}
    Each audio entry:
        {"format_id": str, "ext": str, "abr": float, "filesize": int | None,
         "acodec": str, "label": str}

    Lists are sorted descending by quality (height / bitrate).
    Duplicates within the same resolution+ext or bitrate+ext are deduplicated,
    keeping the entry with the largest filesize.
    """
    raw_formats = info_dict.get("formats") or []

    video_map: dict[tuple[int, str], dict] = {}
    audio_list: dict[tuple[int, str], dict] = {}

    for f in raw_formats:
        fid = f.get("format_id", "")
        ext = f.get("ext", "?")
        vcodec = f.get("vcodec", "none") or "none"
        acodec = f.get("acodec", "none") or "none"
        filesize = f.get("filesize") or f.get("filesize_approx")

        is_video_only = vcodec != "none" and acodec == "none"
        is_audio_only = acodec != "none" and vcodec == "none"

        if is_video_only:
            height = f.get("height") or 0
            if height <= 0:
                continue
            key = (height, ext)
            existing = video_map.get(key)
            if existing is None or (filesize or 0) > (existing["filesize"] or 0):
                res_label = _RESOLUTION_LABELS.get(height, f"{height}p")
                size_str = f" ~{_human_size(filesize)}" if filesize else ""
                codec_short = _short_codec(vcodec)
                label = f"{res_label} / {ext} ({codec_short}{size_str})"
                video_map[key] = {
                    "format_id": fid,
                    "ext": ext,
                    "height": height,
                    "filesize": filesize,
                    "vcodec": vcodec,
                    "label": label,
                }

        elif is_audio_only:
            abr = f.get("abr") or f.get("tbr") or 0
            abr_int = int(abr)
            if abr_int <= 0:
                continue
            key = (abr_int, ext)
            existing = audio_list.get(key)
            if existing is None or (filesize or 0) > (existing["filesize"] or 0):
                codec_short = _short_codec(acodec)
                size_str = f" ~{_human_size(filesize)}" if filesize else ""
                label = f"{abr_int}k / {ext} ({codec_short}{size_str})"
                audio_list[key] = {
                    "format_id": fid,
                    "ext": ext,
                    "abr": float(abr_int),
                    "filesize": filesize,
                    "acodec": acodec,
                    "label": label,
                }

    video_formats = sorted(video_map.values(), key=lambda v: v["height"], reverse=True)
    audio_formats = sorted(audio_list.values(), key=lambda a: a["abr"], reverse=True)
    return video_formats, audio_formats


def build_format_string(video_format_id: str, audio_format_id: str) -> str:
    """Build a yt-dlp format selection string from chosen stream IDs."""
    if video_format_id and audio_format_id:
        return f"{video_format_id}+{audio_format_id}"
    if video_format_id:
        return video_format_id
    if audio_format_id:
        return audio_format_id
    return "best"


def _human_size(nbytes: int | None) -> str:
    if not nbytes:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f}{unit}"
        nbytes = int(nbytes / 1024)
    return f"{nbytes:.1f}TB"


def _short_codec(codec: str) -> str:
    """Shorten codec name for display."""
    if not codec or codec == "none":
        return ""
    codec = codec.lower()
    if codec.startswith("avc") or codec.startswith("h264"):
        return "h264"
    if codec.startswith("hevc") or codec.startswith("h265") or codec.startswith("hev"):
        return "h265"
    if codec.startswith("vp9") or codec.startswith("vp09"):
        return "vp9"
    if codec.startswith("vp8"):
        return "vp8"
    if codec.startswith("av01") or codec == "av1":
        return "av1"
    if codec.startswith("opus"):
        return "opus"
    if codec.startswith("mp4a") or codec.startswith("aac"):
        return "aac"
    if codec.startswith("vorbis"):
        return "vorbis"
    return codec.split(".")[0]


def parse_subtitles(info_dict: dict) -> dict[str, list[dict]]:
    """Parse available subtitle languages from info_dict.

    Returns {"manual": [...], "auto": [...]} where each entry is:
        {"code": str, "name": str}

    Language name is derived from the subtitle metadata or falls back to the code.
    """
    manual_subs = info_dict.get("subtitles") or {}
    auto_subs = info_dict.get("automatic_captions") or {}

    def _extract_langs(subs_dict: dict) -> list[dict]:
        langs = []
        for code, formats in subs_dict.items():
            name = code
            if formats and isinstance(formats, list) and formats[0].get("name"):
                name = formats[0]["name"]
            langs.append({"code": code, "name": name})
        langs.sort(key=lambda x: x["name"].lower())
        return langs

    return {
        "manual": _extract_langs(manual_subs),
        "auto": _extract_langs(auto_subs),
    }


def parse_chapters(info_dict: dict) -> list[dict]:
    """Parse chapters from info_dict.

    Returns a list of:
        {"title": str, "start_time": float, "end_time": float, "index": int}

    Sorted by start_time. Returns empty list if no chapters.
    """
    raw_chapters = info_dict.get("chapters") or []
    chapters = []
    for i, ch in enumerate(raw_chapters):
        title = ch.get("title", f"Chapter {i + 1}")
        start = ch.get("start_time", 0.0)
        end = ch.get("end_time", 0.0)
        chapters.append({
            "title": title,
            "start_time": float(start),
            "end_time": float(end),
            "index": i,
        })
    chapters.sort(key=lambda c: c["start_time"])
    return chapters


_AUDIO_FORMATS = {"mp3", "aac", "flac", "wav", "ogg"}

# Preset shown in the UI; legacy key kept for saved state.json
AUDIO_ONLY_PRESET = "Audio Only"
AUDIO_ONLY_LEGACY_PRESET = "Audio Only (mp3)"
_AUDIO_ONLY_FORMAT = "bestaudio/best"

FORMAT_PRESETS = {
    "Best (video+audio)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
    AUDIO_ONLY_PRESET: _AUDIO_ONLY_FORMAT,
}


def is_audio_only_format(format_key: str) -> bool:
    """True for the audio-only preset (current or legacy saved name)."""
    return format_key in (AUDIO_ONLY_PRESET, AUDIO_ONLY_LEGACY_PRESET)


def normalize_format_preset(format_key: str) -> str:
    """Map legacy preset names to current keys."""
    if format_key == AUDIO_ONLY_LEGACY_PRESET:
        return AUDIO_ONLY_PRESET
    return format_key
