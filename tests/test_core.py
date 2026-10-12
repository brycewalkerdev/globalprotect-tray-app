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

    def test_callback_forwarding(self):
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


if __name__ == "__main__":
    unittest.main()
