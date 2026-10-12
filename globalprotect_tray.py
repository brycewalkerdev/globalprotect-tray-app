#!/usr/bin/env python3
"""Small KDE-friendly tray controller for globalprotect-openconnect."""

from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QLockFile, QProcess, QSettings, QStandardPaths, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSystemTrayIcon,
)


APP_NAME = "GlobalProtect Tray"
APP_ID = "globalprotect-tray"
VERSION = "0.2.0"
DEFAULT_PORTAL = ""
DEFAULT_BROWSER = "default"
DEFAULT_SERVER_MODE = "auto"
DEFAULT_OPENSSL_MODE = "auto"
HELPER = Path("/usr/lib/globalprotect-tray/globalprotect-tray-helper")
PID_FILE = Path("/run/gpclient.lock")
CALLBACK_PORT_FILE = Path("/tmp/gpcallback.port")
AUTOSTART_FILE = Path.home() / ".config/autostart/globalprotect-tray.desktop"
STATE_DIR = Path.home() / ".local/state/globalprotect-tray"


def valid_portal(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def setting_bool(settings: QSettings, key: str, default: bool) -> bool:
    value = settings.value(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def concise_error(stderr: str, fallback: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("Error:"):
            return line.removeprefix("Error:").strip()
    return lines[-1] if lines else fallback


def server_mode(settings: QSettings) -> str:
    value = str(settings.value("server_mode", ""))
    if value in {"auto", "portal", "gateway"}:
        return value
    if settings.contains("direct_gateway"):
        return "gateway" if setting_bool(settings, "direct_gateway", False) else "portal"
    return DEFAULT_SERVER_MODE


def openssl_mode(settings: QSettings) -> str:
    value = str(settings.value("openssl_mode", ""))
    if value in {"auto", "always", "never"}:
        return value
    # Releases before 0.2 always enabled compatibility. Preserve that for
    # existing profiles while defaulting new profiles to automatic detection.
    return "always" if settings.contains("direct_gateway") else DEFAULT_OPENSSL_MODE


def forward_callback(callback_url: str) -> int:
    if not callback_url.startswith("globalprotectcallback:") or len(callback_url) > 1024 * 1024:
        print("globalprotect-tray: invalid authentication callback", file=sys.stderr)
        return 2
    try:
        port = int(CALLBACK_PORT_FILE.read_text(encoding="utf-8").strip())
        if not 1 <= port <= 65535:
            raise ValueError("port out of range")
        with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
            connection.sendall(callback_url.encode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"globalprotect-tray: could not deliver authentication callback: {exc}", file=sys.stderr)
        return 1
    return 0


def ensure_callback_handler() -> None:
    try:
        current = subprocess.run(
            ["/usr/bin/xdg-mime", "query", "default", "x-scheme-handler/globalprotectcallback"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if current in {"", "gpgui.desktop"}:
            subprocess.run(
                [
                    "/usr/bin/xdg-mime",
                    "default",
                    "globalprotect-tray.desktop",
                    "x-scheme-handler/globalprotectcallback",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError:
        pass


def gpclient_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None

    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno != errno.EPERM:
            return None

    try:
        comm = (Path("/proc") / str(pid) / "comm").read_text(encoding="utf-8").strip()
        if comm != "gpclient":
            return None
    except OSError:
        # A live root-owned process may be hidden by a hardened /proc mount.
        pass
    return pid


class ProcessSignals(QObject):
    tunnel_finished = Signal(int)


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None, initial_setup: bool = False) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(f"{APP_NAME} {'Setup' if initial_setup else 'Settings'}")

        self.portal = QLineEdit(str(settings.value("portal", DEFAULT_PORTAL)))
        self.portal.setPlaceholderText("https://vpn.example.edu")
        self.browser = QLineEdit(str(settings.value("browser", DEFAULT_BROWSER)))
        self.browser.setPlaceholderText("default, chrome, firefox, or an executable path")
        self.server_mode = QComboBox()
        self.server_mode.addItem("Auto-detect (recommended)", "auto")
        self.server_mode.addItem("Portal", "portal")
        self.server_mode.addItem("Direct gateway", "gateway")
        self.server_mode.setCurrentIndex(max(0, self.server_mode.findData(server_mode(settings))))
        self.openssl_mode = QComboBox()
        self.openssl_mode.addItem("Auto-detect (recommended)", "auto")
        self.openssl_mode.addItem("Always enable compatibility", "always")
        self.openssl_mode.addItem("Never enable compatibility", "never")
        self.openssl_mode.setCurrentIndex(max(0, self.openssl_mode.findData(openssl_mode(settings))))
        self.autostart = QCheckBox("Start the tray when I log in")
        self.autostart.setChecked(AUTOSTART_FILE.exists())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow("Portal", self.portal)
        layout.addRow("Browser", self.browser)
        layout.addRow("Server type", self.server_mode)
        layout.addRow("Legacy OpenSSL", self.openssl_mode)
        layout.addRow("", self.autostart)
        layout.addRow(buttons)

    def save(self) -> None:
        portal = self.portal.text().strip().rstrip("/")
        browser = self.browser.text().strip() or DEFAULT_BROWSER
        if not valid_portal(portal):
            QMessageBox.warning(self, APP_NAME, "Portal must be a valid https:// URL without credentials.")
            return

        self.settings.setValue("portal", portal)
        self.settings.setValue("browser", browser)
        self.settings.setValue("server_mode", self.server_mode.currentData())
        self.settings.setValue("openssl_mode", self.openssl_mode.currentData())
        self.settings.remove("direct_gateway")
        try:
            set_autostart(self.autostart.isChecked())
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Could not update autostart:\n{exc}")
            return
        self.accept()


def set_autostart(enabled: bool) -> None:
    if not enabled:
        AUTOSTART_FILE.unlink(missing_ok=True)
        return

    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    executable = shutil.which(APP_ID) or str(Path(__file__).resolve())
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={executable}\n"
        "Icon=network-vpn\n"
        "Terminal=false\n"
        "X-KDE-autostart-after=panel\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    AUTOSTART_FILE.write_text(content, encoding="utf-8")


class TrayController(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.settings = QSettings("globalprotect-tray", "globalprotect-tray")
        self.auth_process: QProcess | None = None
        self.tunnel_process: subprocess.Popen[bytes] | None = None
        self.busy_state: str | None = None
        self.auth_gateway = False
        self.auth_openssl = False
        self.auto_gateway_allowed = False
        self.auto_openssl_allowed = False
        self.signals = ProcessSignals()
        self.signals.tunnel_finished.connect(self._tunnel_finished)

        import gi

        gi.require_version("AyatanaAppIndicator3", "0.1")
        gi.require_version("Gtk", "3.0")
        from gi.repository import AyatanaAppIndicator3, GLib, Gtk

        self.appindicator_module = AyatanaAppIndicator3
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            APP_ID,
            "network-vpn-disconnected",
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_title(APP_NAME)
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        self.menu = Gtk.Menu()
        self.status_action = Gtk.MenuItem(label="Disconnected")
        self.status_action.set_sensitive(False)
        self.connect_action = Gtk.MenuItem(label="Connect")
        self.disconnect_action = Gtk.MenuItem(label="Disconnect")
        self.settings_action = Gtk.MenuItem(label="Settings…")
        self.quit_action = Gtk.MenuItem(label="Quit tray")

        self.connect_action.connect("activate", lambda _item: self.connect())
        self.disconnect_action.connect("activate", lambda _item: self.disconnect())
        self.settings_action.connect("activate", lambda _item: self.open_settings())
        self.quit_action.connect("activate", lambda _item: self.quit())

        self.menu.append(self.status_action)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.connect_action)
        self.menu.append(self.disconnect_action)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.settings_action)
        self.menu.append(self.quit_action)
        self.menu.show_all()
        self.indicator.set_menu(self.menu)

        # Qt owns the application loop; briefly service GLib so the exported
        # AppIndicator menu and its callbacks remain responsive.
        self.glib_context = GLib.MainContext.default()
        self.glib_timer = QTimer(self)
        self.glib_timer.setInterval(20)
        self.glib_timer.timeout.connect(self._iterate_glib)
        self.glib_timer.start()

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start()
        self.refresh_status()
        ensure_callback_handler()
        if not valid_portal(self.portal()):
            QTimer.singleShot(250, lambda: self.open_settings(initial_setup=True))

    def _iterate_glib(self) -> None:
        while self.glib_context.pending():
            self.glib_context.iteration(False)

    def portal(self) -> str:
        return str(self.settings.value("portal", DEFAULT_PORTAL)).rstrip("/")

    def browser(self) -> str:
        return str(self.settings.value("browser", DEFAULT_BROWSER)) or DEFAULT_BROWSER

    def server_mode(self) -> str:
        return server_mode(self.settings)

    def openssl_mode(self) -> str:
        return openssl_mode(self.settings)

    def notify(self, title: str, message: str, critical: bool = False) -> None:
        icon_name = "dialog-error" if critical else "network-vpn"
        try:
            subprocess.Popen(
                ["/usr/bin/notify-send", "--app-name", APP_NAME, "--icon", icon_name, title, message],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    def refresh_status(self) -> None:
        connected = gpclient_pid() is not None
        if connected and self.busy_state == "connecting":
            self.busy_state = None
            self.notify(APP_NAME, f"Connected to {urlparse(self.portal()).hostname}")
        if self.busy_state == "authenticating":
            text, icon_name = "Waiting for browser authentication…", "network-vpn-acquiring"
        elif self.busy_state == "connecting":
            text, icon_name = "Connecting…", "network-vpn-acquiring"
        elif self.busy_state == "disconnecting":
            text, icon_name = "Disconnecting…", "network-vpn-acquiring"
        elif connected:
            text, icon_name = f"Connected to {urlparse(self.portal()).hostname}", "network-vpn"
        else:
            text, icon_name = "Disconnected", "network-vpn-disconnected"

        self.status_action.set_label(text)
        self.indicator.set_icon_full(icon_name, text)
        self.connect_action.set_sensitive(not connected and self.busy_state is None)
        self.disconnect_action.set_sensitive(connected or self.busy_state is not None)

    def connect(self) -> None:
        if gpclient_pid() is not None or self.busy_state is not None:
            return
        if not HELPER.is_file():
            QMessageBox.critical(
                None,
                APP_NAME,
                f"The privileged helper is not installed.\n\nRun: sudo ./install.sh\n\nExpected: {HELPER}",
            )
            return
        if not valid_portal(self.portal()):
            QMessageBox.warning(None, APP_NAME, "Open Settings and enter a valid https:// portal URL.")
            return

        self.busy_state = "authenticating"
        self.refresh_status()
        mode = self.server_mode()
        ssl_mode = self.openssl_mode()
        self.auth_gateway = mode == "gateway"
        self.auth_openssl = ssl_mode == "always"
        self.auto_gateway_allowed = mode == "auto"
        self.auto_openssl_allowed = ssl_mode == "auto"
        self._start_authentication()

    def _start_authentication(self) -> None:
        process = QProcess(self)
        process.setProgram("/usr/bin/gpauth")
        auth_args: list[str] = []
        if self.auth_openssl:
            auth_args.append("--fix-openssl")
        if self.auth_gateway:
            auth_args.append("--gateway")
        auth_args.extend([self.portal(), f"--browser={self.browser()}"])
        process.setArguments(auth_args)
        process.finished.connect(self._authentication_finished)
        process.errorOccurred.connect(self._authentication_error)
        self.auth_process = process
        process.start()

    def _authentication_error(self, _error) -> None:
        if self.auth_process is None:
            return
        self.busy_state = None
        detail = self.auth_process.errorString()
        self.auth_process.deleteLater()
        self.auth_process = None
        self.refresh_status()
        self.notify(APP_NAME, f"Could not start authentication: {detail}", True)

    def _authentication_finished(self, exit_code: int, _status) -> None:
        process = self.auth_process
        if process is None:
            return
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        stderr = bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        process.deleteLater()
        self.auth_process = None

        if self.busy_state != "authenticating":
            return
        if exit_code != 0:
            lowered = stderr.lower()
            if (
                not self.auth_openssl
                and self.auto_openssl_allowed
                and "unsafe legacy renegotiation disabled" in lowered
            ):
                self.auth_openssl = True
                self._start_authentication()
                return
            if not self.auth_gateway and self.auto_gateway_allowed and "portal does not exist" in lowered:
                self.auth_gateway = True
                self._start_authentication()
                return
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            (STATE_DIR / "gpauth.log").write_text(stderr, encoding="utf-8")
            self.busy_state = None
            self.refresh_status()
            self.notify(APP_NAME, f"Authentication failed: {concise_error(stderr, 'gpauth exited unexpectedly')}", True)
            return

        auth_line = next((line for line in reversed(stdout.splitlines()) if line.lstrip().startswith("{")), "")
        try:
            auth_data = json.loads(auth_line)
            success = isinstance(auth_data, dict) and ("success" in auth_data or "Success" in auth_data)
            if not success:
                failure = (
                    auth_data.get("failure", auth_data.get("Failure", "Authentication was not completed"))
                    if isinstance(auth_data, dict)
                    else "Invalid response"
                )
                raise ValueError(str(failure))
        except (json.JSONDecodeError, ValueError) as exc:
            self.busy_state = None
            self.refresh_status()
            self.notify(APP_NAME, f"Authentication failed: {exc}", True)
            return

        self.busy_state = "connecting"
        self.refresh_status()
        self._start_tunnel(auth_line)

    def _start_tunnel(self, auth_line: str) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_path = STATE_DIR / "gpclient.log"
        try:
            log_file = log_path.open("ab", buffering=0)
            helper_command = "connect-gateway" if self.auth_gateway else "connect"
            helper_args = ["/usr/bin/pkexec", str(HELPER), helper_command, self.portal()]
            if self.auth_openssl:
                helper_args.append("fix-openssl")
            process = subprocess.Popen(
                helper_args,
                stdin=subprocess.PIPE,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            log_file.close()
            assert process.stdin is not None
            process.stdin.write((auth_line + "\n").encode("utf-8"))
            process.stdin.close()
            self.tunnel_process = process
        except OSError as exc:
            self.busy_state = None
            self.refresh_status()
            self.notify(APP_NAME, f"Could not start the VPN: {exc}", True)
            return

        threading.Thread(target=self._watch_tunnel, args=(process,), daemon=True).start()

    def _watch_tunnel(self, process: subprocess.Popen[bytes]) -> None:
        code = process.wait()
        self.signals.tunnel_finished.emit(code)

    def _tunnel_finished(self, exit_code: int) -> None:
        was_connecting = self.busy_state == "connecting"
        self.tunnel_process = None
        self.busy_state = None
        self.refresh_status()
        if exit_code != 0 and was_connecting:
            self.notify(APP_NAME, "VPN connection failed. See the gpclient log from the tray diagnostics.", True)
        elif not was_connecting:
            self.notify(APP_NAME, "VPN disconnected")

    def disconnect(self) -> None:
        if self.auth_process is not None:
            self.auth_process.kill()
            self.auth_process = None
            self.busy_state = None
            self.refresh_status()
            return
        if self.busy_state == "disconnecting":
            return

        self.busy_state = "disconnecting"
        self.refresh_status()
        try:
            subprocess.Popen(
                ["/usr/bin/pkexec", str(HELPER), "disconnect"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            self.busy_state = None
            self.notify(APP_NAME, f"Could not disconnect: {exc}", True)
            self.refresh_status()
            return
        QTimer.singleShot(1500, self._finish_disconnect)

    def _finish_disconnect(self) -> None:
        if gpclient_pid() is not None:
            QTimer.singleShot(1000, self._finish_disconnect)
            return
        self.busy_state = None
        self.refresh_status()

    def open_settings(self, initial_setup: bool = False) -> None:
        SettingsDialog(self.settings, initial_setup=initial_setup).exec()
        self.refresh_status()

    def quit(self) -> None:
        # Quitting the tray deliberately leaves an established tunnel running.
        if self.auth_process is not None:
            self.auth_process.kill()
        self.indicator.set_status(self.appindicator_module.IndicatorStatus.PASSIVE)
        self.app.quit()


def diagnostics() -> int:
    checks = {
        "gpauth": Path("/usr/bin/gpauth").is_file(),
        "gpclient": Path("/usr/bin/gpclient").is_file(),
        "pkexec": Path("/usr/bin/pkexec").is_file(),
        "privileged helper": HELPER.is_file() and os.access(HELPER, os.X_OK),
        "system tray": QSystemTrayIcon.isSystemTrayAvailable(),
    }
    for name, okay in checks.items():
        print(f"{'OK' if okay else 'MISSING':7} {name}")
    print(f"STATUS  {'connected (PID ' + str(gpclient_pid()) + ')' if gpclient_pid() else 'disconnected'}")
    print(f"LOG     {STATE_DIR / 'gpclient.log'}")
    return 0 if all(checks.values()) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check dependencies and connection state, then exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("callback", nargs="?", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.callback is not None:
        return forward_callback(args.callback)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setQuitOnLastWindowClosed(False)

    if args.check:
        return diagnostics()
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "No system tray is available in this desktop session.")
        return 1

    runtime_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(runtime_dir / "globalprotect-tray.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return 0

    controller = TrayController(app)
    app._tray_controller = controller  # Keep Python ownership for the full event loop.
    app._instance_lock = lock
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
