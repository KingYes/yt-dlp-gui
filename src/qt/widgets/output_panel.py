"""Output folder selection panel."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QPushButton, QWidget

from ...i18n import t


class OutputPanel(QGroupBox):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        on_browse: Callable[[], None],
        on_folder_selected: Callable[[str], None],
    ) -> None:
        super().__init__(t("output.label"), parent)
        layout = QHBoxLayout(self)

        self._folder_combo = QComboBox()
        self._folder_combo.setEditable(False)
        self._folder_combo.currentTextChanged.connect(on_folder_selected)
        layout.addWidget(self._folder_combo, stretch=1)

        self._browse_btn = QPushButton(t("output.browse"))
        self._browse_btn.clicked.connect(on_browse)
        layout.addWidget(self._browse_btn)

        self._folder_menu = _FolderMenuCompat(self._folder_combo)

    def set_folders(self, folders: list[str], current: str) -> None:
        self._folder_combo.blockSignals(True)
        self._folder_combo.clear()
        if folders:
            self._folder_combo.addItems(folders)
        if current:
            idx = self._folder_combo.findText(current)
            if idx >= 0:
                self._folder_combo.setCurrentIndex(idx)
            else:
                self._folder_combo.insertItem(0, current)
                self._folder_combo.setCurrentIndex(0)
        self._folder_combo.blockSignals(False)

    def current_folder(self) -> str:
        return self._folder_combo.currentText()

    def retranslate_ui(self) -> None:
        self.setTitle(t("output.label"))
        self._browse_btn.setText(t("output.browse"))


class _FolderMenuCompat:
    """CTk OptionMenu.configure(values=...) compatibility."""

    def __init__(self, combo: QComboBox) -> None:
        self._combo = combo

    def configure(self, values: list[str] | None = None, **kwargs: object) -> None:
        if values is not None:
            current = self._combo.currentText()
            self._combo.clear()
            if values:
                self._combo.addItems(values)
            if current and self._combo.findText(current) < 0:
                self._combo.insertItem(0, current)
            if self._combo.count() > 0 and not self._combo.currentText():
                self._combo.setCurrentIndex(0)
