from unittest.mock import MagicMock, patch

from tray import TrayManager, _create_icon_image


class TestCreateIconImage:
    def test_returns_rgba_image(self) -> None:
        img = _create_icon_image(64)
        assert img.mode == "RGBA"
        assert img.size == (64, 64)

    def test_custom_size(self) -> None:
        img = _create_icon_image(128)
        assert img.size == (128, 128)


class TestTrayManagerAvailability:
    def test_available_when_pystray_imported(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        assert tm.available is True

    def test_start_creates_icon(self) -> None:
        with patch("tray.pystray") as mock_pystray:
            mock_icon = MagicMock()
            mock_pystray.Icon.return_value = mock_icon
            mock_pystray.Menu = MagicMock()
            mock_pystray.MenuItem = MagicMock()

            tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
            tm.start()

            mock_pystray.Icon.assert_called_once()
            assert tm._icon is mock_icon

    def test_stop_calls_icon_stop(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        mock_icon = MagicMock()
        tm._icon = mock_icon

        tm.stop()
        mock_icon.stop.assert_called_once()
        assert tm._icon is None

    def test_stop_when_no_icon(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        tm.stop()  # should not raise


class TestTrayManagerTooltip:
    def test_update_tooltip_stores_value(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        tm.update_tooltip("Downloading 3/5")
        assert tm._tooltip == "Downloading 3/5"

    def test_update_tooltip_sets_icon_title(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        mock_icon = MagicMock()
        tm._icon = mock_icon
        tm.update_tooltip("test tooltip")
        assert mock_icon.title == "test tooltip"


class TestTrayManagerNotify:
    def test_notify_calls_icon(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        mock_icon = MagicMock()
        tm._icon = mock_icon
        tm.notify("Title", "Message")
        mock_icon.notify.assert_called_once_with("Message", "Title")

    def test_notify_without_icon_does_not_raise(self) -> None:
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
        tm.notify("Title", "Message")  # should not raise


class TestTrayManagerCallbacks:
    def test_show_action_calls_on_show(self) -> None:
        called = []
        tm = TrayManager(on_show=lambda: called.append("show"), on_quit=lambda: None)
        tm._show_action(MagicMock(), MagicMock())
        assert called == ["show"]

    def test_quit_action_calls_on_quit(self) -> None:
        called = []
        tm = TrayManager(on_show=lambda: None, on_quit=lambda: called.append("quit"))
        tm._quit_action(MagicMock(), MagicMock())
        assert called == ["quit"]

    def test_double_start_is_noop(self) -> None:
        with patch("tray.pystray") as mock_pystray:
            mock_icon = MagicMock()
            mock_pystray.Icon.return_value = mock_icon
            mock_pystray.Menu = MagicMock()
            mock_pystray.MenuItem = MagicMock()

            tm = TrayManager(on_show=lambda: None, on_quit=lambda: None)
            tm.start()
            tm.start()  # second start should be no-op

            assert mock_pystray.Icon.call_count == 1
