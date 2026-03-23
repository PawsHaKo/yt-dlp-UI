import json
import os
import threading
import tempfile
import unittest
from urllib import request, error

import server


class FakeEditManager:
    def __init__(self, downloads_dir: str):
        self.downloads_dir = downloads_dir
        self.previews: dict[str, dict] = {}

    def create_preview(self, source_file, delete_ranges, gain_db, output_format):
        source_path = os.path.join(self.downloads_dir, source_file)
        if not os.path.isfile(source_path):
            raise FileNotFoundError("找不到來源檔案")
        if output_format not in {"mp3", "m4a"}:
            raise ValueError("不支援的輸出格式")

        preview_id = f"preview-{len(self.previews) + 1}"
        preview_path = os.path.join(self.downloads_dir, f"{preview_id}.{output_format}")
        with open(preview_path, "wb") as handle:
            handle.write(b"fake-audio")

        self.previews[preview_id] = {
            "preview_id": preview_id,
            "source_file": source_file,
            "source_path": source_path,
            "preview_path": preview_path,
            "output_format": output_format,
        }
        return {
            "preview_id": preview_id,
            "preview_url": f"/edits/previews/{preview_id}",
            "source_file": source_file,
            "output_format": output_format,
        }

    def get_preview(self, preview_id):
        preview = self.previews.get(preview_id)
        if not preview:
            return None
        return dict(preview)

    def delete_preview(self, preview_id):
        preview = self.previews.pop(preview_id, None)
        if not preview:
            return False
        if os.path.exists(preview["preview_path"]):
            os.remove(preview["preview_path"])
        return True

    def commit_preview(self, preview_id, mode, target_name=None):
        preview = self.previews.get(preview_id)
        if not preview:
            raise KeyError("找不到預覽")

        if mode == "overwrite":
            source_ext = os.path.splitext(preview["source_file"])[1].lstrip(".").lower()
            if source_ext != preview["output_format"]:
                raise ValueError("覆蓋模式必須與原始格式一致")
            backup_name = f"{preview['source_file']}.bak.test"
            self.delete_preview(preview_id)
            return {
                "file_name": preview["source_file"],
                "file_url": f"/downloads/{preview['source_file']}",
                "backup_file": backup_name,
            }

        target_file = target_name or f"edited.{preview['output_format']}"
        self.delete_preview(preview_id)
        return {
            "file_name": target_file,
            "file_url": f"/downloads/{target_file}",
            "backup_file": None,
        }

    def shutdown(self):
        for preview_id in list(self.previews.keys()):
            self.delete_preview(preview_id)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.manager = server.JobManager(downloads_dir=cls._tmpdir.name, max_workers=0)
        cls.edit_manager = FakeEditManager(cls._tmpdir.name)
        handler = server.create_request_handler(cls.manager, cls.edit_manager)
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

        with open(os.path.join(cls._tmpdir.name, "sample.mp3"), "wb") as handle:
            handle.write(b"source-audio")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.edit_manager.shutdown()
        cls.manager.shutdown()
        cls._tmpdir.cleanup()

    def request_json(self, method: str, path: str, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            method=method,
            data=data,
            headers=headers,
        )

        try:
            with request.urlopen(req) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body) if body else None
                return response.status, parsed
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            parsed = json.loads(body) if body else None
            return exc.code, parsed

    def test_post_and_get_jobs(self):
        status, payload = self.request_json(
            "POST",
            "/jobs",
            {"urls": ["https://youtube.com/watch?v=abc", "https://youtube.com/watch?v=abc"]},
        )

        self.assertEqual(status, 201)
        self.assertEqual(len(payload["jobs"]), 1)

        get_status, jobs = self.request_json("GET", "/jobs")

        self.assertEqual(get_status, 200)
        self.assertGreaterEqual(len(jobs), 1)
        self.assertEqual(jobs[-1]["url"], "https://youtube.com/watch?v=abc")

    def test_retry_endpoint_creates_new_job(self):
        create_status, payload = self.request_json(
            "POST",
            "/jobs",
            {"urls": ["https://youtu.be/retry-me"]},
        )
        self.assertEqual(create_status, 201)

        original_job = payload["jobs"][0]
        self.manager.update_job(original_job["id"], status="failed", error="test failure")

        retry_status, retried = self.request_json("POST", f"/jobs/{original_job['id']}/retry")

        self.assertEqual(retry_status, 201)
        self.assertEqual(retried["url"], original_job["url"])
        self.assertNotEqual(retried["id"], original_job["id"])
        self.assertEqual(retried["status"], "queued")

    def test_preview_commit_and_delete_endpoints(self):
        status, preview = self.request_json(
            "POST",
            "/edits/preview",
            {
                "source_file": "sample.mp3",
                "delete_ranges": [{"start_sec": 1, "end_sec": 2}],
                "gain_db": 1.5,
                "output_format": "mp3",
            },
        )
        self.assertEqual(status, 201)
        self.assertIn("preview_id", preview)

        get_req = request.Request(
            f"http://127.0.0.1:{self.port}{preview['preview_url']}",
            method="GET",
        )
        with request.urlopen(get_req) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.read())

        commit_status, committed = self.request_json(
            "POST",
            "/edits/commit",
            {
                "preview_id": preview["preview_id"],
                "mode": "save_as",
                "target_name": "my-edit.mp3",
            },
        )
        self.assertEqual(commit_status, 200)
        self.assertEqual(committed["file_name"], "my-edit.mp3")

        delete_status, _ = self.request_json(
            "DELETE",
            f"/edits/previews/{preview['preview_id']}",
        )
        self.assertEqual(delete_status, 404)

    def test_commit_overwrite_format_mismatch_returns_400(self):
        status, preview = self.request_json(
            "POST",
            "/edits/preview",
            {
                "source_file": "sample.mp3",
                "delete_ranges": [],
                "gain_db": 0,
                "output_format": "m4a",
            },
        )
        self.assertEqual(status, 201)

        commit_status, payload = self.request_json(
            "POST",
            "/edits/commit",
            {
                "preview_id": preview["preview_id"],
                "mode": "overwrite",
            },
        )
        self.assertEqual(commit_status, 400)
        self.assertIn("覆蓋模式", payload["error"])


if __name__ == "__main__":
    unittest.main()
