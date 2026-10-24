import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import subprocess

from PySide6.QtCore import QSettings


ROOT = Path(__file__).resolve().parents[1]


def load_file(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


tray = load_file("globalprotect_tray", ROOT / "globalprotect_tray.py")
helper = load_file("globalprotect_tray_helper", ROOT / "globalprotect-tray-helper")


class CoreTests(unittest.TestCase):
    def test_portal_validation(self):
        self.assertTrue(tray.valid_portal("https://vpn.example.edu"))
        self.assertTrue(tray.valid_portal("https://vpn.example.edu/path"))
        self.assertFalse(tray.valid_portal("http://vpn.example.edu"))
        self.assertFalse(tray.valid_portal("https://user:password@vpn.example.edu"))

    def test_mode_defaults_and_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            self.assertEqual(tray.server_mode(settings), "auto")
            self.assertEqual(tray.openssl_mode(settings), "auto")
            settings.setValue("direct_gateway", True)
            self.assertEqual(tray.server_mode(settings), "gateway")
            self.assertEqual(tray.openssl_mode(settings), "always")

    def test_concise_error(self):
        stderr = "INFO starting\nError: portal does not exist\n"
        self.assertEqual(tray.concise_error(stderr, "fallback"), "portal does not exist")

    def test_auth_result_case_compatibility(self):
        for key in ("success", "Success"):
            previous = sys.stdin
            try:
                data = json.dumps({key: {"username": "test", "token": "long-token"}}) + "\n"
                sys.stdin = io.TextIOWrapper(io.BytesIO(data.encode()))
                self.assertTrue(helper.read_auth())
            finally:
                sys.stdin = previous

    def test_callback_rejects_invalid_scheme(self):
        self.assertEqual(tray.forward_callback("https://example.edu"), 2)

    @patch.object(tray, "native_callback_available", return_value=False)
    def test_callback_forwarding(self, _native):
        received = []
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)

        def receive():
            connection, _address = listener.accept()
            with connection:
                received.append(connection.recv(4096).decode())
            listener.close()

        thread = threading.Thread(target=receive)
        thread.start()
        previous = tray.CALLBACK_PORT_FILE
        with tempfile.TemporaryDirectory() as directory:
            try:
                tray.CALLBACK_PORT_FILE = Path(directory) / "callback.port"
                tray.CALLBACK_PORT_FILE.write_text(str(listener.getsockname()[1]), encoding="utf-8")
                callback = "globalprotectcallback:test-auth-data"
                self.assertEqual(tray.forward_callback(callback), 0)
            finally:
                tray.CALLBACK_PORT_FILE = previous
        thread.join(timeout=2)
        self.assertEqual(received, [callback])

    def test_native_callback_capability(self):
        for status in (0, 2):
            tray.native_callback_available.cache_clear()
            with patch.object(tray.subprocess, "run", return_value=subprocess.CompletedProcess([], status)) as run:
                self.assertEqual(tray.native_callback_available(), status == 0)
                tray.native_callback_available()
                run.assert_called_once()
        tray.native_callback_available.cache_clear()

    @patch.object(tray, "native_callback_available", return_value=True)
    def test_native_callback_forwarding_preserves_argument_and_exit_status(self, _native):
        callback = "globalprotectcallback:cas-as=1&un=test&token=example"
        with patch.object(tray.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)) as run:
            self.assertEqual(tray.forward_callback(callback), 7)
            self.assertEqual(run.call_args.args[0], ["/usr/bin/gpauth", "auth-callback", callback])

    @patch.object(tray, "native_callback_available", return_value=True)
    def test_native_callback_failure_does_not_log_credentials(self, _native):
        with patch.object(tray.subprocess, "run", side_effect=subprocess.TimeoutExpired("gpauth", 10)):
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(tray.forward_callback("globalprotectcallback:secret"), 1)
                self.assertNotIn("secret", stderr.getvalue())

    def test_desktop_repair_preserves_metadata_and_existing_user_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "system/applications/gpgui.desktop"
            source.parent.mkdir(parents=True)
            original = '[Desktop Entry]\nName=GP Connect\nExec="/usr/bin/gpclient" launch-gui %u\n'
            source.write_text(original)
            with patch.dict(tray.os.environ, {"XDG_DATA_HOME": str(root / "user"), "XDG_DATA_DIRS": str(root / "system")}):
                tray.repair_native_desktop_entry()
                target = root / "user/applications/gpgui.desktop"
                self.assertEqual(target.read_text(), original.replace('"/usr/bin/gpclient"', '/usr/bin/gpclient'))
                self.assertEqual(source.read_text(), original)
                target.write_text("user customization")
                tray.repair_native_desktop_entry()
                self.assertEqual(target.read_text(), "user customization")

    def test_desktop_repair_ignores_unrelated_launchers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "system/applications/gpgui.desktop"
            source.parent.mkdir(parents=True)
            source.write_text('[Desktop Entry]\nExec="/opt/custom path/gpclient" launch-gui %u\n')
            with patch.dict(tray.os.environ, {"XDG_DATA_HOME": str(root / "user"), "XDG_DATA_DIRS": str(root / "system")}):
                tray.repair_native_desktop_entry()
                self.assertFalse((root / "user/applications/gpgui.desktop").exists())

    def test_handler_selection_and_migration(self):
        for native, current, expected in (
            (True, "globalprotect-tray.desktop", "gpgui.desktop"),
            (True, "gpgui.desktop", None),
            (False, "gpgui.desktop", "globalprotect-tray.desktop"),
            (True, "other.desktop", None),
        ):
            with self.subTest(native=native, current=current):
                with patch.object(tray, "native_callback_available", return_value=native), \
                     patch.object(tray, "repair_native_desktop_entry"), \
                     patch.object(tray.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=current)) as run:
                    tray.ensure_callback_handler()
                    if expected:
                        self.assertEqual(run.call_args.args[0][1:3], ["default", expected])
                    else:
                        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
