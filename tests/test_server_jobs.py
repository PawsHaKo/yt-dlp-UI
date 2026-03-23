import unittest

import server


class UrlNormalizationTests(unittest.TestCase):
    def test_normalize_urls_trims_and_deduplicates(self):
        raw_urls = [
            " https://youtube.com/watch?v=abc ",
            "https://youtube.com/watch?v=abc",
            "",
            "   ",
            "https://youtu.be/xyz",
        ]

        normalized = server.normalize_urls(raw_urls)

        self.assertEqual(
            normalized,
            [
                "https://youtube.com/watch?v=abc",
                "https://youtu.be/xyz",
            ],
        )


class ProgressParsingTests(unittest.TestCase):
    def test_parse_download_progress_line(self):
        line = "[download]  42.1% of 5.01MiB at 1.34MiB/s ETA 00:02"

        parsed = server.parse_yt_dlp_line(line)

        self.assertEqual(parsed["status"], "downloading")
        self.assertEqual(parsed["progress"], 42)
        self.assertEqual(parsed["speed"], "1.34MiB/s")
        self.assertEqual(parsed["eta"], "00:02")

    def test_parse_postprocess_line(self):
        line = "[ExtractAudio] Destination: downloads/my-song.mp3"

        parsed = server.parse_yt_dlp_line(line)

        self.assertEqual(parsed["status"], "postprocessing")
        self.assertEqual(parsed["progress"], 100)
        self.assertIsNone(parsed["speed"])
        self.assertIsNone(parsed["eta"])
        self.assertEqual(parsed["file_name"], "my-song.mp3")


class JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = server.JobManager(max_workers=0)

    def tearDown(self):
        self.manager.shutdown()

    def test_create_jobs_are_queued(self):
        created = self.manager.create_jobs(
            [
                "https://youtube.com/watch?v=abc",
                "https://youtube.com/watch?v=abc",
                "https://youtu.be/xyz",
            ]
        )

        self.assertEqual(len(created), 2)
        self.assertTrue(all(job["status"] == "queued" for job in created))
        self.assertTrue(all(isinstance(job["id"], str) and job["id"] for job in created))

    def test_list_jobs_can_filter_by_ids(self):
        created = self.manager.create_jobs(
            ["https://youtube.com/watch?v=abc", "https://youtu.be/xyz"]
        )
        selected_id = created[1]["id"]

        result = self.manager.list_jobs(ids=[selected_id])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], selected_id)

    def test_retry_reuses_same_job_for_failed_job(self):
        created = self.manager.create_jobs(["https://youtube.com/watch?v=abc"])
        job_id = created[0]["id"]
        self.manager.update_job(job_id, status="failed", error="network error")
        before_count = len(self.manager.list_jobs())

        retried = self.manager.retry_job(job_id)
        after_count = len(self.manager.list_jobs())

        self.assertEqual(retried["id"], job_id)
        self.assertEqual(retried["url"], created[0]["url"])
        self.assertEqual(retried["status"], "queued")
        self.assertEqual(retried["progress"], 0)
        self.assertIsNone(retried["error"])
        self.assertEqual(before_count, after_count)

    def test_delete_job_removes_non_running_job(self):
        created = self.manager.create_jobs(["https://youtube.com/watch?v=abc"])
        job_id = created[0]["id"]

        removed = self.manager.delete_job(job_id)

        self.assertEqual(removed["id"], job_id)
        self.assertIsNone(self.manager.get_job(job_id))

    def test_delete_job_rejects_downloading_job(self):
        created = self.manager.create_jobs(["https://youtube.com/watch?v=abc"])
        job_id = created[0]["id"]
        self.manager.update_job(job_id, status="downloading")

        with self.assertRaises(ValueError):
            self.manager.delete_job(job_id)

    def test_set_concurrency_limit_updates_value(self):
        manager = server.JobManager(max_workers=3, concurrency_limit=1)
        self.addCleanup(manager.shutdown)

        before = manager.get_concurrency_settings()
        self.assertEqual(before["max_concurrent_jobs"], 1)
        self.assertEqual(before["max_allowed"], 3)

        updated = manager.set_concurrency_limit(2)
        self.assertEqual(updated["max_concurrent_jobs"], 2)
        self.assertEqual(updated["max_allowed"], 3)


class EditHelpersTests(unittest.TestCase):
    def test_normalize_delete_ranges_sorts_merges_and_clamps(self):
        result = server.normalize_delete_ranges(
            [
                {"start_sec": 20, "end_sec": 30},
                {"start_sec": -10, "end_sec": 5},
                {"start_sec": 4, "end_sec": 10},
                {"start_sec": 9, "end_sec": 12},
                {"start_sec": 35, "end_sec": 999},
            ],
            duration_sec=40,
        )

        self.assertEqual(result, [(0.0, 12.0), (20.0, 30.0), (35.0, 40.0)])

    def test_build_keep_ranges_from_delete_ranges(self):
        keep = server.build_keep_ranges(
            duration_sec=50,
            delete_ranges=[(5.0, 10.0), (20.0, 25.0), (30.0, 40.0)],
        )

        self.assertEqual(keep, [(0.0, 5.0), (10.0, 20.0), (25.0, 30.0), (40.0, 50.0)])

    def test_build_filter_complex_contains_concat_and_volume(self):
        filter_text = server.build_filter_complex([(0.0, 4.5), (9.0, 12.0)], gain_db=3)

        self.assertIn("concat=n=2:v=0:a=1", filter_text)
        self.assertIn("volume=3.00dB[out]", filter_text)


if __name__ == "__main__":
    unittest.main()
