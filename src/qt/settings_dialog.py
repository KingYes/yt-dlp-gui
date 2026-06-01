"""Qt settings dialog."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..i18n import get_available_languages, t
from ..settings_constants import _BROWSER_LABELS, _BROWSERS, _THEMES
from ..state import AppState
from .theme import apply_theme, apply_ui_scale, muted_color


class SettingsDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        state: AppState,
        *,
        on_theme_changed: Callable[[], None] | None = None,
        on_clipboard_changed: Callable[[bool], None] | None = None,
        on_language_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._settings: dict[str, Any] = dict(state.settings)
        self._on_theme_changed = on_theme_changed
        self._on_clipboard_changed = on_clipboard_changed
        self._on_language_changed = on_language_changed

        self.setWindowTitle(t("settings.title"))
        self.setMinimumSize(420, 540)
        self.resize(480, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        layout.addWidget(self._appearance_group())
        layout.addWidget(self._download_group())
        layout.addWidget(self._network_group())
        layout.addWidget(self._advanced_group())
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        close_btn = QPushButton(t("settings.ok"))
        close_btn.clicked.connect(self.accept)
        outer.addWidget(close_btn)

    def _appearance_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.appearance"))
        form = QFormLayout(group)

        theme_labels = [t("settings.theme_system"), t("settings.theme_dark"), t("settings.theme_light")]
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(theme_labels)
        current_theme = self._settings.get("theme", "system")
        theme_idx = _THEMES.index(current_theme) if current_theme in _THEMES else 0
        self._theme_combo.setCurrentIndex(theme_idx)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_change)
        form.addRow(t("settings.theme"), self._theme_combo)

        available_langs = get_available_languages()
        self._lang_codes = [code for code, _ in available_langs]
        lang_labels = [name for _, name in available_langs]
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(lang_labels)
        current_lang = self._settings.get("language", "en")
        lang_idx = self._lang_codes.index(current_lang) if current_lang in self._lang_codes else 0
        self._lang_combo.setCurrentIndex(lang_idx)
        self._lang_combo.currentIndexChanged.connect(self._on_language_change)
        form.addRow(t("settings.language"), self._lang_combo)

        scale_row = QHBoxLayout()
        current_scale = float(self._settings.get("ui_scale", 1.0))
        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setRange(80, 150)
        self._scale_slider.setValue(int(current_scale * 100))
        self._scale_slider.valueChanged.connect(self._on_scale_change)
        self._scale_label = QLabel(f"{int(current_scale * 100)}%")
        self._scale_label.setFixedWidth(45)
        scale_row.addWidget(self._scale_slider)
        scale_row.addWidget(self._scale_label)
        form.addRow(t("settings.ui_scale"), scale_row)

        return group

    def _download_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.download_defaults"))
        form = QFormLayout(group)

        self._speed_entry = QLineEdit()
        self._speed_entry.setPlaceholderText(t("settings.speed_limit_placeholder"))
        self._speed_entry.setText(self._settings.get("speed_limit", ""))
        self._speed_entry.editingFinished.connect(
            lambda: self._save_text("speed_limit", self._speed_entry.text().strip())
        )
        form.addRow(t("settings.speed_limit"), self._speed_entry)

        self._embed_thumb = QCheckBox(t("settings.embed_thumbnail"))
        self._embed_thumb.setChecked(self._settings.get("embed_thumbnail", False))
        self._embed_thumb.toggled.connect(lambda v: self._state.save_settings(embed_thumbnail=v))
        form.addRow(self._embed_thumb)

        self._embed_meta = QCheckBox(t("settings.embed_metadata"))
        self._embed_meta.setChecked(self._settings.get("embed_metadata", False))
        self._embed_meta.toggled.connect(lambda v: self._state.save_settings(embed_metadata=v))
        form.addRow(self._embed_meta)

        self._subtitle_lang_entry = QLineEdit()
        self._subtitle_lang_entry.setPlaceholderText(t("settings.subtitle_languages_placeholder"))
        self._subtitle_lang_entry.setText(self._settings.get("subtitle_languages", "en"))
        self._subtitle_lang_entry.editingFinished.connect(
            lambda: self._save_text("subtitle_languages", self._subtitle_lang_entry.text().strip())
        )
        form.addRow(t("settings.subtitle_languages"), self._subtitle_lang_entry)

        self._clipboard_check = QCheckBox(t("settings.clipboard_monitor"))
        self._clipboard_check.setChecked(self._settings.get("clipboard_monitor", False))
        self._clipboard_check.toggled.connect(self._on_clipboard_toggle)
        form.addRow(self._clipboard_check)

        self._minimize_tray_check = QCheckBox(t("settings.minimize_to_tray"))
        self._minimize_tray_check.setChecked(self._settings.get("minimize_to_tray", False))
        self._minimize_tray_check.toggled.connect(
            lambda v: self._state.save_settings(minimize_to_tray=v)
        )
        form.addRow(self._minimize_tray_check)

        return group

    def _network_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.network"))
        form = QFormLayout(group)

        self._proxy_entry = QLineEdit()
        self._proxy_entry.setPlaceholderText(t("settings.proxy_placeholder"))
        self._proxy_entry.setText(self._settings.get("proxy", ""))
        self._proxy_entry.editingFinished.connect(
            lambda: self._save_text("proxy", self._proxy_entry.text().strip())
        )
        form.addRow(t("settings.proxy"), self._proxy_entry)

        self._browser_combo = QComboBox()
        self._browser_combo.addItems(_BROWSER_LABELS)
        current_browser = self._settings.get("browser_cookies", "")
        browser_idx = _BROWSERS.index(current_browser) if current_browser in _BROWSERS else 0
        self._browser_combo.setCurrentIndex(browser_idx)
        self._browser_combo.currentIndexChanged.connect(self._on_browser_change)
        form.addRow(t("settings.browser_cookies"), self._browser_combo)

        help_browser = QLabel(t("settings.browser_cookies_help"))
        help_browser.setWordWrap(True)
        help_browser.setStyleSheet(f"color: {muted_color().name()}; font-size: 11px;")
        form.addRow(help_browser)

        cookie_row = QHBoxLayout()
        self._cookie_entry = QLineEdit()
        self._cookie_entry.setPlaceholderText(t("settings.cookie_file_placeholder"))
        self._cookie_entry.setText(self._settings.get("cookie_file", ""))
        self._cookie_entry.editingFinished.connect(
            lambda: self._save_text("cookie_file", self._cookie_entry.text().strip())
        )
        browse_btn = QPushButton(t("settings.cookie_file_browse"))
        browse_btn.clicked.connect(self._browse_cookie_file)
        cookie_row.addWidget(self._cookie_entry)
        cookie_row.addWidget(browse_btn)
        form.addRow(t("settings.cookie_file"), cookie_row)

        help_cookie = QLabel(t("settings.cookie_file_help"))
        help_cookie.setWordWrap(True)
        help_cookie.setStyleSheet(f"color: {muted_color().name()}; font-size: 11px;")
        form.addRow(help_cookie)

        return group

    def _advanced_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.advanced"))
        form = QFormLayout(group)

        self._portable_check = QCheckBox(t("settings.portable_mode"))
        self._portable_check.setChecked(self._settings.get("portable_mode", False))
        self._portable_check.toggled.connect(self._on_portable_toggle)
        form.addRow(self._portable_check)

        help_portable = QLabel(t("settings.portable_help"))
        help_portable.setWordWrap(True)
        help_portable.setStyleSheet(f"color: {muted_color().name()}; font-size: 11px;")
        form.addRow(help_portable)

        return group

    def _save_text(self, key: str, value: str) -> None:
        self._state.save_settings(**{key: value})

    def _on_theme_change(self, index: int) -> None:
        theme = _THEMES[index] if 0 <= index < len(_THEMES) else "system"
        self._state.save_settings(theme=theme)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, self._state.settings)
        if self._on_theme_changed:
            self._on_theme_changed()

    def _on_scale_change(self, value: int) -> None:
        scale = round(value / 100.0, 2)
        self._scale_label.setText(f"{value}%")
        self._state.save_settings(ui_scale=scale)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_ui_scale(app, self._state.settings)

    def _on_clipboard_toggle(self, enabled: bool) -> None:
        self._state.save_settings(clipboard_monitor=enabled)
        if self._on_clipboard_changed:
            self._on_clipboard_changed(enabled)

    def _on_browser_change(self, index: int) -> None:
        browser = _BROWSERS[index] if 0 <= index < len(_BROWSERS) else ""
        self._state.save_settings(browser_cookies=browser)

    def _on_language_change(self, index: int) -> None:
        if index < 0 or index >= len(self._lang_codes):
            return
        code = self._lang_codes[index]
        self._state.save_settings(language=code)
        if self._on_language_changed:
            self.accept()
            self._on_language_changed(code)

    def _on_portable_toggle(self, enabled: bool) -> None:
        if enabled:
            self._state.enable_portable_mode()
        else:
            self._state.disable_portable_mode()

    def _browse_cookie_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings.cookie_file_dialog_title"),
            "",
            f"{t('settings.cookie_file_dialog_text')} (*.txt);;{t('settings.cookie_file_dialog_all')} (*.*)",
        )
        if path:
            self._cookie_entry.setText(path)
            self._state.save_settings(cookie_file=path)
