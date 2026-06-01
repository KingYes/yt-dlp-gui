# Agent Guidelines

## Project Overview

yt-dlp GUI is a cross-platform desktop application built with Python 3.12+ and PySide6 (Qt). It wraps yt-dlp to provide a graphical interface for downloading videos, audio, and playlists.

## Architecture

- **Entry point**: `main.py` → `src/qt/app.py` (`run_qt_app`).
- **UI layer**: `src/qt/` — `MainWindow` coordinates widget panels in `src/qt/widgets/`.
- **Download engine**: `src/download_manager.py` (yt-dlp wrapper, runs in daemon threads), `src/download_handler.py` (orchestrates downloads and calls back into `DownloadContext`).
- **`DownloadContext` protocol**: `src/download_context.py` defines the interface; `src/qt/qt_download_context.py` is the Qt implementation.
- **Thread marshalling**: Worker threads call `_schedule_on_main(func)` which emits a `Signal(object)`. The main thread's `_exec_on_main` slot executes the callback.
- **Theming**: `src/qt/theme.py` — Fusion style with dark/light palettes, semantic color helpers, and baseline-aware UI scaling.
- **i18n**: `src/i18n.py` — JSON locale files in `locales/`, `t("key")` for translations, `is_rtl()` for layout direction.
- **State**: `src/state.py` (`AppState`) — JSON-based settings and queue persistence.

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
- Gracefully degrade when optional dependencies are missing (`tkinterdnd2`).
- Use semantic color helpers from `src/qt/theme.py` (`danger_color()`, `success_color()`, etc.) instead of hardcoded hex colors.
