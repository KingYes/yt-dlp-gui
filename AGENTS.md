# Agent Guidelines

## Project Overview

yt-dlp GUI is a cross-platform desktop application built with Python 3.12+ and PySide6 (Qt). Download orchestration goes through `DownloadContext` (see `src/download_handler.py`, `src/download_progress.py`). It wraps yt-dlp to provide a graphical interface for downloading videos, audio, and playlists.

## Conventions

- **Python**: 3.12+ with type hints on all function signatures.
- **Linting**: ruff (config in `pyproject.toml`). Run `ruff check .` to lint.
- **Type checking**: mypy (config in `pyproject.toml`).
- **Tests**: pytest; optional Qt tests via `pip install -r requirements-dev.txt` (`pytest-qt`). Test files live in `tests/`. Run with `pytest`.
- **Manual UI testing**: `python main.py` or the **Run yt-dlp GUI** launch config.
- **Dependencies**: runtime deps in `requirements.txt`, dev deps in `requirements-dev.txt`, no `setup.py`.

## Key Rules

- When adding or changing a user-facing feature, update the Features section in `README.md`. See `.cursor/rules/update-readme-on-feature.mdc`.
- Keep the version in `src/updater.py` (`APP_VERSION`) and `pyproject.toml` (`version`) in sync. The `bump.yml` workflow handles this automatically for releases.
- All downloads run in background threads — never block the main (UI) thread.
