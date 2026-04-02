import http.server
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib import request, error

import server


class MockSynologyHandler(http.server.BaseHTTPRequestHandler):
    """Simulates a Synology FileStation API server."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if "/auth.cgi" in self.path:
            if "method=login" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": {"sid": "mock-sid-12345"},
                }).encode())
                return
            if "method=logout" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
                return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if "/entry.cgi" in self.path:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")
            has_file = b'name="file"' in body
            has_api = b"SYNO.FileStation.Upload" in body

            if "multipart/form-data" in content_type and has_file and has_api:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": {"code": 400},
                }).encode())
            return
        self.send_response(404)
        self.end_headers()


class NasClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._mock_httpd = http.server.HTTPServer(("127.0.0.1", 0), MockSynologyHandler)
        cls._mock_port = cls._mock_httpd.server_address[1]
        cls._mock_thread = threading.Thread(target=cls._mock_httpd.serve_forever, daemon=True)
        cls._mock_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._mock_httpd.shutdown()
        cls._mock_httpd.server_close()

    def _make_client(self, **kwargs):
        defaults = {
            "host": "127.0.0.1",
            "port": str(self._mock_port),
            "upload_path": "/music/downloads",
            "scheme": "http",
        }
        defaults.update(kwargs)
        return server.NasClient(**defaults)

    def test_token_mode_upload(self):
        client = self._make_client(token="my-token")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"audio-data")
            path = f.name
        try:
            result = client.upload(path)
            self.assertTrue(result["success"])
            self.assertEqual(result["upload_path"], "/music/downloads")
        finally:
            os.unlink(path)

    def test_password_mode_upload(self):
        client = self._make_client(user="admin", password="secret")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"audio-data")
            path = f.name
        try:
            result = client.upload(path)
            self.assertTrue(result["success"])
        finally:
            os.unlink(path)

    def test_scheme_used_in_base_url(self):
        client_http = self._make_client(scheme="http", token="t")
        self.assertTrue(client_http.base_url.startswith("http://"))

        client_https = self._make_client(scheme="https", token="t")
        self.assertTrue(client_https.base_url.startswith("https://"))

    def test_auth_mode_reflects_credentials(self):
        self.assertEqual(self._make_client(token="t").auth_mode, "token")
        self.assertEqual(self._make_client(user="u", password="p").auth_mode, "password")


class NasFromEnvTests(unittest.TestCase):
    def test_from_env_reads_scheme(self):
        env = {
            "NAS_HOST": "10.0.0.1",
            "NAS_PORT": "5000",
            "NAS_UPLOAD_PATH": "/share",
            "NAS_USER": "admin",
            "NAS_PASSWORD": "pass",
            "NAS_SCHEME": "http",
        }
        with patch.dict(os.environ, env, clear=False):
            client = server.NasClient.from_env()
        self.assertIsNotNone(client)
        self.assertEqual(client.scheme, "http")
        self.assertTrue(client.base_url.startswith("http://"))

    def test_from_env_defaults_to_https(self):
        env = {
            "NAS_HOST": "10.0.0.1",
            "NAS_PORT": "5001",
            "NAS_UPLOAD_PATH": "/share",
            "NAS_TOKEN": "abc",
        }
        with patch.dict(os.environ, env, clear=False):
            client = server.NasClient.from_env()
        self.assertEqual(client.scheme, "https")

    def test_from_env_returns_none_when_missing_keys(self):
        with patch.dict(os.environ, {"NAS_HOST": "x"}, clear=True):
            self.assertIsNone(server.NasClient.from_env())


class LoadDotenvTests(unittest.TestCase):
    def test_load_dotenv_sets_env_vars(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write('MY_TEST_KEY=hello\nMY_OTHER="world"\n# comment\n')
            path = f.name
        try:
            with patch.dict(os.environ, {}, clear=False):
                server.load_dotenv(path)
                self.assertEqual(os.environ.get("MY_TEST_KEY"), "hello")
                self.assertEqual(os.environ.get("MY_OTHER"), "world")
        finally:
            os.unlink(path)
            os.environ.pop("MY_TEST_KEY", None)
            os.environ.pop("MY_OTHER", None)

    def test_load_dotenv_does_not_override_existing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("PATH=/fake\n")
            path = f.name
        try:
            original_path = os.environ.get("PATH")
            server.load_dotenv(path)
            self.assertEqual(os.environ.get("PATH"), original_path)
        finally:
            os.unlink(path)

    def test_load_dotenv_missing_file_is_noop(self):
        server.load_dotenv("/nonexistent/.env")


class NasUploadEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._mock_httpd = http.server.HTTPServer(("127.0.0.1", 0), MockSynologyHandler)
        cls._mock_port = cls._mock_httpd.server_address[1]
        cls._mock_thread = threading.Thread(target=cls._mock_httpd.serve_forever, daemon=True)
        cls._mock_thread.start()

        cls._tmpdir = tempfile.TemporaryDirectory()
        with open(os.path.join(cls._tmpdir.name, "song.mp3"), "wb") as f:
            f.write(b"test-audio")

        cls.job_manager = server.JobManager(downloads_dir=cls._tmpdir.name, max_workers=0)
        cls.nas_client = server.NasClient(
            host="127.0.0.1", port=str(cls._mock_port),
            upload_path="/music", scheme="http", token="test-token",
        )
        handler = server.create_request_handler(cls.job_manager, nas_client=cls.nas_client)
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._mock_httpd.shutdown()
        cls._mock_httpd.server_close()
        cls.job_manager.shutdown()
        cls._tmpdir.cleanup()

    def _post(self, path, payload):
        data = json.dumps(payload).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            method="POST", data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_upload_succeeds(self):
        status, data = self._post("/nas/upload", {"file_name": "song.mp3"})
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

    def test_upload_missing_file_returns_404(self):
        status, data = self._post("/nas/upload", {"file_name": "nope.mp3"})
        self.assertEqual(status, 404)

    def test_upload_missing_filename_returns_400(self):
        status, data = self._post("/nas/upload", {})
        self.assertEqual(status, 400)

    def test_nas_status_returns_available(self):
        req = request.Request(f"http://127.0.0.1:{self.port}/nas/status")
        with request.urlopen(req) as resp:
            data = json.loads(resp.read())
        self.assertTrue(data["available"])


if __name__ == "__main__":
    unittest.main()
