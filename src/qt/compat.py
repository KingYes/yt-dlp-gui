"""Thin adapters so DownloadHandler can drive Qt widgets with CTk-like calls."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QWidget


class LabelCompat:
    def __init__(self, label: QLabel) -> None:
        self._label = label

    def configure(self, text: str | None = None, **kwargs: object) -> None:
        if text is not None:
            self._label.setText(text)


class ButtonCompat:
    def __init__(self, button: QPushButton) -> None:
        self._button = button

    def configure(self, state: str | None = None, **kwargs: object) -> None:
        if state is not None:
            self._button.setEnabled(state != "disabled")


class ProgressBarCompat:
    def __init__(self, bar: QProgressBar) -> None:
        self._bar = bar
        self._indeterminate = False

    def set(self, fraction: float) -> None:
        if not self._indeterminate:
            self._bar.setValue(min(100, max(0, int(fraction * 100))))

    def configure(self, mode: str | None = None, **kwargs: object) -> None:
        if mode == "indeterminate":
            self._bar.setRange(0, 0)
            self._indeterminate = True
        elif mode == "determinate":
            self._bar.setRange(0, 100)
            self._indeterminate = False

    def start(self) -> None:
        self.configure(mode="indeterminate")

    def stop(self) -> None:
        self.configure(mode="determinate")
        self._bar.setValue(0)

    def cget(self, key: str) -> str:
        if key == "mode":
            return "indeterminate" if self._indeterminate else "determinate"
        return ""


class BooleanVarCompat:
    def __init__(self, getter: Callable[[], bool], setter: Callable[[bool], None]) -> None:
        self._get = getter
        self._set = setter

    def get(self) -> bool:
        return self._get()

    def set(self, value: bool) -> None:
        self._set(value)


class StringVarCompat:
    def __init__(self, getter: Callable[[], str], setter: Callable[[str], None]) -> None:
        self._get = getter
        self._set = setter

    def get(self) -> str:
        return self._get()

    def set(self, value: str) -> None:
        self._set(value)


class EntryCompat:
    def __init__(self, getter: Callable[[], str], setter: Callable[[str], None]) -> None:
        self._get = getter
        self._set = setter

    def get(self) -> str:
        return self._get()

    def insert(self, _index: int, text: str) -> None:
        self._set(text)

    def delete(self, _start: int, _end: int) -> None:
        self._set("")
