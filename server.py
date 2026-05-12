import datetime
import http.server
import json
import os
import queue
import re
import shutil
import socketserver
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any

PORT = 8000
DOWNLOADS_DIR = "downloads"
DEFAULT_CONCURRENT_JOBS = 1
MAX_WORKER_THREADS = 3
DEFAULT_COOKIES_FILE = "www.youtube.com_cookies.txt"
DEFAULT_FAILED_JOBS_FILE = os.path.join("job_state", "failed_jobs.json")
DEFAULT_YTDLP_UPDATE_COMMAND = ["brew", "upgrade", "yt-dlp"]
DEFAULT_YTDLP_UPDATE_OUTPUT_LIMIT = 12000

PREVIEW_DIR_NAME = ".tmp-edits"
PREVIEW_TTL_SECONDS = 2 * 60 * 60
PREVIEW_CLEANUP_INTERVAL_SECONDS = 10 * 60

NAS_ENV_KEYS = ("NAS_HOST", "NAS_PORT", "NAS_UPLOAD_PATH")


def load_dotenv(path: str = ".env") -> None:
    """Load variables from a .env file into os.environ (no-op if file missing)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if not key:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except FileNotFoundError:
        pass

DOWNLOAD_PERCENT_RE = re.compile(r"\[download\]\s+(?P<percent>\d+(?:\.\d+)?)%")
SPEED_RE = re.compile(r"\sat\s+(?P<speed>\S+)")
ETA_RE = re.compile(r"\sETA\s+(?P<eta>\S+)")
EXTRACT_AUDIO_RE = re.compile(r"\[ExtractAudio\]\s+Destination:\s+(?P<path>.+)")

OUTPUT_FORMATS = {
    "mp3": {
        "codec": "libmp3lame",
        "content_type": "audio/mpeg",
    },
    "m4a": {
        "codec": "aac",
        "content_type": "audio/mp4",
    },
}


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def is_valid_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []

    for raw_url in urls:
        url = raw_url.strip()
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        normalized.append(url)

    return normalized


def parse_yt_dlp_line(line: str) -> dict[str, Any] | None:
    if not line:
        return None

    match = DOWNLOAD_PERCENT_RE.search(line)
    if match:
        percent = int(float(match.group("percent")))
        speed_match = SPEED_RE.search(line)
        eta_match = ETA_RE.search(line)
        return {
            "status": "downloading",
            "progress": max(0, min(percent, 100)),
            "speed": speed_match.group("speed") if speed_match else None,
            "eta": eta_match.group("eta") if eta_match else None,
        }

    extract_match = EXTRACT_AUDIO_RE.search(line)
    if extract_match:
        destination = extract_match.group("path").strip()
        return {
            "status": "postprocessing",
            "progress": 100,
            "speed": None,
            "eta": None,
            "file_name": os.path.basename(destination),
        }

    if "[ExtractAudio]" in line or "[Merger]" in line:
        return {
            "status": "postprocessing",
            "progress": 100,
            "speed": None,
            "eta": None,
        }

    return None


def sanitize_file_name(file_name: str) -> str:
    if not isinstance(file_name, str):
        raise ValueError("檔名格式錯誤")

    cleaned = file_name.strip()
    if not cleaned:
        raise ValueError("檔名不可為空")
    if cleaned in {".", ".."}:
        raise ValueError("檔名不合法")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError("檔名不合法")

    return cleaned


def resolve_file_path(downloads_dir: str, file_name: str) -> tuple[str, str]:
    safe_name = sanitize_file_name(file_name)
    base_dir = os.path.abspath(downloads_dir)
    full_path = os.path.abspath(os.path.join(base_dir, safe_name))
    if not full_path.startswith(base_dir + os.sep):
        raise ValueError("檔案路徑不合法")

    return full_path, safe_name


def normalize_delete_ranges(
    ranges: list[dict[str, Any]],
    duration_sec: float,
) -> list[tuple[float, float]]:
    if not isinstance(ranges, list):
        raise ValueError("delete_ranges 必須是陣列")

    normalized: list[tuple[float, float]] = []
    for item in ranges:
        if not isinstance(item, dict):
            raise ValueError("delete_ranges 內容格式錯誤")

        start_raw = item.get("start_sec")
        end_raw = item.get("end_sec")
        if not isinstance(start_raw, (int, float)) or not isinstance(end_raw, (int, float)):
            raise ValueError("start_sec 與 end_sec 必須是數字")

        start = max(0.0, min(float(start_raw), duration_sec))
        end = max(0.0, min(float(end_raw), duration_sec))
        if end <= start:
            continue

        normalized.append((start, end))

    normalized.sort(key=lambda pair: pair[0])
    merged: list[tuple[float, float]] = []
    for start, end in normalized:
        if not merged:
            merged.append((start, end))
            continue

        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def build_keep_ranges(
    duration_sec: float,
    delete_ranges: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    cursor = 0.0
    keep_ranges: list[tuple[float, float]] = []

    for start, end in delete_ranges:
        if start > cursor:
            keep_ranges.append((cursor, start))
        cursor = max(cursor, end)

    if cursor < duration_sec:
        keep_ranges.append((cursor, duration_sec))

    return [(start, end) for start, end in keep_ranges if end - start > 0.0001]


def build_filter_complex(keep_ranges: list[tuple[float, float]], gain_db: float) -> str:
    if not keep_ranges:
        raise ValueError("刪除區段覆蓋整段音訊，無可輸出內容")

    segment_filters: list[str] = []
    labels: list[str] = []
    for index, (start, end) in enumerate(keep_ranges):
        label = f"s{index}"
        labels.append(label)
        segment_filters.append(
            f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[{label}]"
        )

    if len(labels) == 1:
        join_filter = f"[{labels[0]}]anull[trimmed]"
    else:
        concat_inputs = "".join(f"[{label}]" for label in labels)
        join_filter = f"{concat_inputs}concat=n={len(labels)}:v=0:a=1[trimmed]"

    volume_filter = f"[trimmed]volume={float(gain_db):.2f}dB[out]"
    return ";".join(segment_filters + [join_filter, volume_filter])


def probe_audio_info(source_path: str, ffprobe_path: str) -> dict[str, Any]:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        source_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "ffprobe failed"
        raise RuntimeError(message)

    payload = json.loads(result.stdout)
    fmt = payload.get("format", {}) if isinstance(payload, dict) else {}
    streams = payload.get("streams", []) if isinstance(payload, dict) else []
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})

    duration_raw = fmt.get("duration") or audio_stream.get("duration")
    if duration_raw is None:
        raise ValueError("無法取得音訊長度")

    duration = float(duration_raw)
    if duration <= 0:
        raise ValueError("音訊長度不合法")

    bit_rate_raw = audio_stream.get("bit_rate") or fmt.get("bit_rate")
    bit_rate: int | None = None
    if bit_rate_raw not in {None, ""}:
        bit_rate = int(float(bit_rate_raw))

    extension = os.path.splitext(source_path)[1].lower().lstrip(".")
    return {
        "duration_sec": duration,
        "bit_rate": bit_rate,
        "extension": extension,
    }


class JobManager:
    def __init__(
        self,
        downloads_dir: str = DOWNLOADS_DIR,
        yt_dlp_path: str = "./yt-dlp",
        max_workers: int = MAX_WORKER_THREADS,
        concurrency_limit: int | None = None,
        cookies_file: str | None = None,
        failed_jobs_file: str | None = None,
    ):
        self.downloads_dir = downloads_dir
        self.yt_dlp_path = yt_dlp_path
        self.max_workers = max(0, int(max_workers))
        self.cookies_file = cookies_file
        self.failed_jobs_file = failed_jobs_file
        if self.max_workers <= 0:
            self._concurrency_limit = 0
        else:
            requested_limit = (
                DEFAULT_CONCURRENT_JOBS if concurrency_limit is None else int(concurrency_limit)
            )
            self._concurrency_limit = max(1, min(requested_limit, self.max_workers))
        self._active_jobs = 0

        self._lock = threading.Lock()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._shutdown_event = threading.Event()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._job_order: list[str] = []
        self._persisted_failed_jobs: dict[str, dict[str, Any]] = {}
        self._workers: list[threading.Thread] = []
        self._slot_condition = threading.Condition()

        os.makedirs(self.downloads_dir, exist_ok=True)
        self._load_persisted_failed_jobs()

        for index in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"job-worker-{index}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def shutdown(self) -> None:
        self._shutdown_event.set()
        with self._slot_condition:
            self._slot_condition.notify_all()
        for _ in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join(timeout=2)

    def get_concurrency_settings(self) -> dict[str, int]:
        with self._slot_condition:
            return {
                "max_concurrent_jobs": self._concurrency_limit,
                "max_allowed": self.max_workers,
            }

    def set_concurrency_limit(self, limit: int) -> dict[str, int]:
        if self.max_workers <= 0:
            raise ValueError("目前不支援背景工作執行緒")

        value = int(limit)
        if value < 1 or value > self.max_workers:
            raise ValueError(f"max_concurrent_jobs 必須介於 1 到 {self.max_workers}")

        with self._slot_condition:
            self._concurrency_limit = value
            self._slot_condition.notify_all()

        return self.get_concurrency_settings()

    def create_jobs(self, urls: list[str]) -> list[dict[str, Any]]:
        valid_urls = [url for url in normalize_urls(urls) if is_valid_url(url)]
        created_jobs: list[dict[str, Any]] = []

        with self._lock:
            for url in valid_urls:
                job = self._new_job(url)
                self._jobs[job["id"]] = job
                self._job_order.append(job["id"])
                created_jobs.append(dict(job))

        for job in created_jobs:
            if self.max_workers > 0:
                self._queue.put(job["id"])

        return created_jobs

    def list_jobs(self, ids: list[str] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            ordered_ids = self._ordered_job_ids_locked()
            if ids is not None:
                filter_ids = set(ids)
                ordered_ids = [job_id for job_id in ordered_ids if job_id in filter_ids]

            return [dict(self._jobs[job_id]) for job_id in ordered_ids if job_id in self._jobs]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def update_job(self, job_id: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            job.update(updates)
            self._sync_persisted_failed_job_locked(job_id)
            return dict(job)

    def retry_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            if job.get("status") != "failed":
                raise ValueError("Only failed jobs can be retried")

            job.update(
                status="queued",
                progress=0,
                speed=None,
                eta=None,
                file_name=None,
                error=None,
            )
            retried_id = str(job["id"])

        if self.max_workers > 0:
            self._queue.put(retried_id)

        return self.get_job(retried_id) or {}

    def delete_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)

            status = str(job.get("status", ""))
            if status in {"downloading", "postprocessing"}:
                raise ValueError("下載中的任務不可刪除")

            removed = dict(job)
            del self._jobs[job_id]
            self._job_order = [item for item in self._job_order if item != job_id]
            if self._persisted_failed_jobs.pop(job_id, None) is not None:
                self._write_failed_jobs_locked()

        return removed

    def _ordered_job_ids_locked(self) -> list[str]:
        existing_ids = [job_id for job_id in self._job_order if job_id in self._jobs]
        failed_ids = [
            job_id
            for job_id in existing_ids
            if self._jobs[job_id].get("status") == "failed"
        ]
        other_ids = [
            job_id
            for job_id in existing_ids
            if self._jobs[job_id].get("status") != "failed"
        ]
        return failed_ids + other_ids

    def _load_persisted_failed_jobs(self) -> None:
        if not self.failed_jobs_file or not os.path.isfile(self.failed_jobs_file):
            return

        try:
            with open(self.failed_jobs_file, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, list):
            return

        for item in payload:
            if not isinstance(item, dict):
                continue
            job_id = item.get("id")
            url = item.get("url")
            if not isinstance(job_id, str) or not job_id:
                continue
            if not isinstance(url, str) or not is_valid_url(url):
                continue
            if job_id in self._jobs:
                continue

            progress = item.get("progress")
            if not isinstance(progress, (int, float)):
                progress = 0

            created_at = item.get("created_at")
            if not isinstance(created_at, str) or not created_at:
                created_at = utc_now_iso()

            error = item.get("error")
            if error is not None and not isinstance(error, str):
                error = str(error)

            file_name = item.get("file_name")
            if file_name is not None and not isinstance(file_name, str):
                file_name = None

            job = {
                "id": job_id,
                "url": url,
                "status": "failed",
                "progress": max(0, min(int(progress), 100)),
                "speed": None,
                "eta": None,
                "file_name": file_name,
                "error": error,
                "created_at": created_at,
            }
            self._jobs[job_id] = job
            self._job_order.append(job_id)
            self._persisted_failed_jobs[job_id] = dict(job)

    def _sync_persisted_failed_job_locked(self, job_id: str) -> None:
        if not self.failed_jobs_file:
            return

        job = self._jobs.get(job_id)
        if not job:
            return

        status = str(job.get("status", ""))
        if status == "failed":
            self._persisted_failed_jobs[job_id] = dict(job)
            self._write_failed_jobs_locked()
            return

        if status == "completed" and self._persisted_failed_jobs.pop(job_id, None) is not None:
            self._write_failed_jobs_locked()

    def _write_failed_jobs_locked(self) -> None:
        if not self.failed_jobs_file:
            return

        state_dir = os.path.dirname(os.path.abspath(self.failed_jobs_file))
        os.makedirs(state_dir, exist_ok=True)
        ordered_failed_jobs = [
            dict(self._persisted_failed_jobs[job_id])
            for job_id in self._job_order
            if job_id in self._persisted_failed_jobs
        ]
        temp_path = f"{self.failed_jobs_file}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(ordered_failed_jobs, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, self.failed_jobs_file)

    def _new_job(self, url: str) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "url": url,
            "status": "queued",
            "progress": 0,
            "speed": None,
            "eta": None,
            "file_name": None,
            "error": None,
            "created_at": utc_now_iso(),
        }

    def _worker_loop(self) -> None:
        while not self._shutdown_event.is_set():
            job_id = self._queue.get()
            if job_id is None:
                self._queue.task_done()
                break

            try:
                self._acquire_download_slot()
                self._run_job(job_id)
            finally:
                self._release_download_slot()
                self._queue.task_done()

    def _acquire_download_slot(self) -> None:
        with self._slot_condition:
            while (
                not self._shutdown_event.is_set()
                and self._active_jobs >= self._concurrency_limit
            ):
                self._slot_condition.wait(timeout=0.2)
            self._active_jobs += 1

    def _release_download_slot(self) -> None:
        with self._slot_condition:
            self._active_jobs = max(0, self._active_jobs - 1)
            self._slot_condition.notify_all()

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if not job:
            return

        self.update_job(
            job_id,
            status="downloading",
            progress=0,
            speed=None,
            eta=None,
            error=None,
        )

        command = [
            self.yt_dlp_path,
            "--newline",
            "-x",
            "--audio-format",
            "mp3",
            "-o",
            os.path.join(self.downloads_dir, "%(title)s.%(ext)s"),
            job["url"],
        ]
        if self.cookies_file:
            command[1:1] = ["--cookies", self.cookies_file]

        last_line = ""

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.strip()
                    if line:
                        last_line = line
                    parsed = parse_yt_dlp_line(line)
                    if parsed:
                        self.update_job(job_id, **parsed)

            return_code = process.wait()
            if return_code == 0:
                self.update_job(
                    job_id,
                    status="completed",
                    progress=100,
                    speed=None,
                    eta=None,
                    error=None,
                )
            else:
                self.update_job(
                    job_id,
                    status="failed",
                    speed=None,
                    eta=None,
                    error=last_line or f"yt-dlp exited with code {return_code}",
                )
        except Exception as exc:
            self.update_job(
                job_id,
                status="failed",
                speed=None,
                eta=None,
                error=str(exc),
            )


class EditManager:
    def __init__(
        self,
        downloads_dir: str,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        preview_dir_name: str = PREVIEW_DIR_NAME,
        preview_ttl_seconds: int = PREVIEW_TTL_SECONDS,
        cleanup_interval_seconds: int = PREVIEW_CLEANUP_INTERVAL_SECONDS,
    ):
        self.downloads_dir = downloads_dir
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.preview_ttl_seconds = max(1, int(preview_ttl_seconds))
        self.cleanup_interval_seconds = max(0, int(cleanup_interval_seconds))

        self.preview_dir = os.path.join(downloads_dir, preview_dir_name)
        os.makedirs(self.preview_dir, exist_ok=True)

        self._lock = threading.Lock()
        self._previews: dict[str, dict[str, Any]] = {}
        self._shutdown_event = threading.Event()
        self._cleanup_thread: threading.Thread | None = None

        if self.cleanup_interval_seconds > 0:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                name="preview-cleanup",
                daemon=True,
            )
            self._cleanup_thread.start()

    def shutdown(self) -> None:
        self._shutdown_event.set()
        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=2)

    def _cleanup_loop(self) -> None:
        while not self._shutdown_event.wait(self.cleanup_interval_seconds):
            self.cleanup_expired()

    def _build_preview_path(self, output_format: str) -> str:
        return os.path.join(self.preview_dir, f"{uuid.uuid4()}.{output_format}")

    def _bitrate_kbps(self, bit_rate: int | None) -> str:
        if bit_rate is None or bit_rate <= 0:
            return "192k"

        kbps = int(round(bit_rate / 1000))
        kbps = max(64, min(kbps, 320))
        return f"{kbps}k"

    def create_preview(
        self,
        source_file: str,
        delete_ranges: list[dict[str, Any]],
        gain_db: float,
        output_format: str,
    ) -> dict[str, Any]:
        output_format = str(output_format).lower()
        if output_format not in OUTPUT_FORMATS:
            raise ValueError("不支援的輸出格式")

        source_path, safe_name = resolve_file_path(self.downloads_dir, source_file)
        if not os.path.isfile(source_path):
            raise FileNotFoundError("找不到來源檔案")

        info = probe_audio_info(source_path, self.ffprobe_path)
        duration = float(info["duration_sec"])

        merged_delete_ranges = normalize_delete_ranges(delete_ranges, duration)
        keep_ranges = build_keep_ranges(duration, merged_delete_ranges)
        filter_complex = build_filter_complex(keep_ranges, float(gain_db))

        format_config = OUTPUT_FORMATS[output_format]
        preview_path = self._build_preview_path(output_format)

        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            source_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-vn",
            "-acodec",
            format_config["codec"],
            "-b:a",
            self._bitrate_kbps(info.get("bit_rate")),
            preview_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "ffmpeg failed"
            raise RuntimeError(message)

        preview_id = str(uuid.uuid4())
        now = time.time()
        record = {
            "preview_id": preview_id,
            "source_file": safe_name,
            "source_path": source_path,
            "preview_path": preview_path,
            "output_format": output_format,
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            self._previews[preview_id] = record

        return {
            "preview_id": preview_id,
            "preview_url": f"/edits/previews/{preview_id}",
            "source_file": safe_name,
            "output_format": output_format,
        }

    def get_preview(self, preview_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._previews.get(preview_id)
            if not record:
                return None
            return dict(record)

    def _remove_preview_record(self, preview_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._previews.pop(preview_id, None)

    def delete_preview(self, preview_id: str) -> bool:
        record = self._remove_preview_record(preview_id)
        if not record:
            return False

        preview_path = record.get("preview_path")
        if isinstance(preview_path, str) and os.path.exists(preview_path):
            os.remove(preview_path)

        return True

    def cleanup_expired(self, max_age_seconds: int | None = None) -> int:
        ttl = self.preview_ttl_seconds if max_age_seconds is None else int(max_age_seconds)
        now = time.time()
        to_delete: list[str] = []

        with self._lock:
            for preview_id, record in self._previews.items():
                updated_at = float(record.get("updated_at", record.get("created_at", 0.0)))
                if now - updated_at > ttl:
                    to_delete.append(preview_id)

        removed = 0
        for preview_id in to_delete:
            if self.delete_preview(preview_id):
                removed += 1

        return removed

    def commit_preview(
        self,
        preview_id: str,
        mode: str,
        target_name: str | None = None,
    ) -> dict[str, Any]:
        record = self.get_preview(preview_id)
        if not record:
            raise KeyError("找不到預覽")

        preview_path = record["preview_path"]
        source_path = record["source_path"]
        source_file = record["source_file"]
        output_format = record["output_format"]

        if not os.path.isfile(preview_path):
            self._remove_preview_record(preview_id)
            raise FileNotFoundError("找不到預覽檔")

        mode = str(mode)
        if mode not in {"save_as", "overwrite"}:
            raise ValueError("mode 必須是 save_as 或 overwrite")

        source_ext = os.path.splitext(source_file)[1].lower().lstrip(".")

        if mode == "overwrite":
            if output_format != source_ext:
                raise ValueError("覆蓋模式必須與原始格式一致")

            os.replace(preview_path, source_path)
            self._remove_preview_record(preview_id)

            return {
                "file_name": source_file,
                "file_url": f"/downloads/{urllib.parse.quote(source_file)}",
                "backup_file": None,
            }

        final_name: str
        if target_name is None or not str(target_name).strip():
            stem = os.path.splitext(source_file)[0]
            final_name = f"{stem}_edited_{timestamp_slug()}.{output_format}"
        else:
            final_name = sanitize_file_name(str(target_name).strip())
            ext = os.path.splitext(final_name)[1].lower().lstrip(".")
            if not ext:
                final_name = f"{final_name}.{output_format}"
            elif ext != output_format:
                raise ValueError("target_name 副檔名需與輸出格式一致")

        target_path, final_name = resolve_file_path(self.downloads_dir, final_name)
        if os.path.exists(target_path):
            raise FileExistsError("目標檔案已存在")

        shutil.copy2(preview_path, target_path)
        os.remove(preview_path)
        self._remove_preview_record(preview_id)

        return {
            "file_name": final_name,
            "file_url": f"/downloads/{urllib.parse.quote(final_name)}",
            "backup_file": None,
        }


def parse_json_body(handler: http.server.BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length_raw = handler.headers.get("Content-Length", "0")
    content_length = int(content_length_raw)
    raw_body = handler.rfile.read(content_length)
    if not raw_body:
        return {}
    return json.loads(raw_body)


class NasClient:
    """Synology FileStation API client for uploading files.

    Supports two auth modes:
    - Token mode (DSM 7+): set NAS_TOKEN env var
    - Password mode (DSM 6+): set NAS_USER + NAS_PASSWORD env vars
    Token takes priority when both are set.
    """

    def __init__(self, host: str, port: str, upload_path: str, *,
                 scheme: str = "https",
                 token: str | None = None, user: str | None = None, password: str | None = None) -> None:
        self.scheme = scheme
        self.base_url = f"{scheme}://{host}:{port}/webapi"
        self.upload_path = upload_path
        self.token = token
        self.user = user
        self.password = password
        self.auth_mode = "token" if token else "password"

    def _login(self) -> str:
        params = urllib.parse.urlencode({
            "api": "SYNO.API.Auth",
            "version": "3",
            "method": "login",
            "account": self.user,
            "passwd": self.password,
            "session": "FileStation",
            "format": "sid",
        })
        url = f"{self.base_url}/auth.cgi?{params}"
        req = urllib.request.Request(url)
        ctx = self._ssl_context() if self.scheme == "https" else None
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = json.loads(resp.read())
        if not data.get("success"):
            error_code = data.get("error", {}).get("code", "unknown")
            raise RuntimeError(f"NAS login failed (error code: {error_code})")
        return data["data"]["sid"]

    def _logout(self, sid: str) -> None:
        params = urllib.parse.urlencode({
            "api": "SYNO.API.Auth",
            "version": "3",
            "method": "logout",
            "session": "FileStation",
            "_sid": sid,
        })
        url = f"{self.base_url}/auth.cgi?{params}"
        try:
            req = urllib.request.Request(url)
            ctx = self._ssl_context() if self.scheme == "https" else None
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                resp.read()
        except Exception:
            pass

    def upload(self, file_path: str) -> dict[str, Any]:
        if self.token:
            return self._upload_file(self.token, file_path)
        sid = self._login()
        try:
            return self._upload_file(sid, file_path)
        finally:
            self._logout(sid)

    def list_files(self) -> list[str]:
        if self.token:
            return self._list_files(self.token)
        sid = self._login()
        try:
            return self._list_files(sid)
        finally:
            self._logout(sid)

    def _upload_file(self, sid: str, file_path: str) -> dict[str, Any]:
        boundary = uuid.uuid4().hex
        file_name = os.path.basename(file_path)

        parts: list[bytes] = []
        for name, value in [("api", "SYNO.FileStation.Upload"), ("version", "2"),
                            ("method", "upload"), ("path", self.upload_path),
                            ("create_parents", "true"), ("overwrite", "true"),
                            ("_sid", sid)]:
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
            )

        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        with open(file_path, "rb") as f:
            file_data = f.read()
        parts.append(file_data)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)

        qs = urllib.parse.urlencode({"_sid": sid})
        url = f"{self.base_url}/entry.cgi?{qs}"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("Cookie", f"id={sid}")
        ctx = self._ssl_context() if self.scheme == "https" else None
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            data = json.loads(resp.read())

        if not data.get("success"):
            error_code = data.get("error", {}).get("code", "unknown")
            raise RuntimeError(f"NAS upload failed (error code: {error_code})")

        return {"success": True, "file_name": file_name, "upload_path": self.upload_path}

    def _list_files(self, sid: str) -> list[str]:
        params = urllib.parse.urlencode({
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": self.upload_path,
            "_sid": sid,
        })
        url = f"{self.base_url}/entry.cgi?{params}"
        req = urllib.request.Request(url)
        req.add_header("Cookie", f"id={sid}")
        ctx = self._ssl_context() if self.scheme == "https" else None
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read())

        if not data.get("success"):
            error_code = data.get("error", {}).get("code", "unknown")
            raise RuntimeError(f"NAS list files failed (error code: {error_code})")

        raw_files = data.get("data", {}).get("files", [])
        if not isinstance(raw_files, list):
            return []

        file_names: list[str] = []
        for item in raw_files:
            if not isinstance(item, dict) or item.get("isdir"):
                continue
            name = item.get("name")
            if isinstance(name, str) and name:
                file_names.append(name)
        return file_names

    @staticmethod
    def _ssl_context():
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @staticmethod
    def from_env() -> "NasClient | None":
        values = {k: os.environ.get(k) for k in NAS_ENV_KEYS}
        if not all(values.values()):
            return None
        token = os.environ.get("NAS_TOKEN")
        user = os.environ.get("NAS_USER")
        password = os.environ.get("NAS_PASSWORD")
        if not token and not (user and password):
            return None
        scheme = os.environ.get("NAS_SCHEME", "https").lower()
        return NasClient(
            host=values["NAS_HOST"],
            port=values["NAS_PORT"],
            upload_path=values["NAS_UPLOAD_PATH"],
            scheme=scheme,
            token=token,
            user=user,
            password=password,
        )


class YtDlpUpdater:
    def __init__(
        self,
        command: list[str] | None = None,
        runner=None,
        output_limit: int = DEFAULT_YTDLP_UPDATE_OUTPUT_LIMIT,
    ):
        self.command = list(command or DEFAULT_YTDLP_UPDATE_COMMAND)
        self.runner = runner or self._default_runner
        self.output_limit = max(1, int(output_limit))
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "status": "idle",
            "running": False,
            "started_at": None,
            "finished_at": None,
            "return_code": None,
            "output": "",
            "command": list(self.command),
        }

    @staticmethod
    def _default_runner(command: list[str]):
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_locked(started=False)

    def start_update(self) -> dict[str, Any]:
        with self._lock:
            if self._status["running"]:
                return self._snapshot_locked(started=False)

            self._status.update(
                {
                    "status": "running",
                    "running": True,
                    "started_at": utc_now_iso(),
                    "finished_at": None,
                    "return_code": None,
                    "output": "",
                    "command": list(self.command),
                }
            )
            thread = threading.Thread(target=self._run_update, name="yt-dlp-updater", daemon=True)
            self._thread = thread
            payload = self._snapshot_locked(started=True)

        thread.start()
        return payload

    def wait(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _run_update(self) -> None:
        return_code: int | None = None
        output = ""
        status = "failed"

        try:
            result = self.runner(list(self.command))
            return_code = int(getattr(result, "returncode", 1))
            stdout = getattr(result, "stdout", "") or ""
            stderr = getattr(result, "stderr", "") or ""
            output = self._bounded_output(stdout, stderr)
            status = "succeeded" if return_code == 0 else "failed"
        except Exception as exc:
            output = self._bounded_output("", f"{type(exc).__name__}: {exc}")

        with self._lock:
            self._status.update(
                {
                    "status": status,
                    "running": False,
                    "finished_at": utc_now_iso(),
                    "return_code": return_code,
                    "output": output,
                }
            )

    def _bounded_output(self, stdout: str, stderr: str) -> str:
        combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
        if len(combined) <= self.output_limit:
            return combined
        return combined[-self.output_limit:]

    def _snapshot_locked(self, started: bool) -> dict[str, Any]:
        payload = dict(self._status)
        payload["command"] = list(self.command)
        payload["started"] = started
        return payload


def create_request_handler(
    job_manager: JobManager,
    edit_manager: EditManager | None = None,
    nas_client: NasClient | None = None,
    yt_dlp_updater: YtDlpUpdater | None = None,
):
    if edit_manager is None:
        edit_manager = EditManager(downloads_dir=job_manager.downloads_dir)
    if yt_dlp_updater is None:
        yt_dlp_updater = YtDlpUpdater()

    class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
        def _send_json(self, payload: Any, status_code: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_preview_file(self, preview: dict[str, Any]) -> None:
            preview_path = preview.get("preview_path")
            if not isinstance(preview_path, str) or not os.path.isfile(preview_path):
                self._send_json({"error": "找不到預覽檔"}, status_code=404)
                return

            output_format = str(preview.get("output_format", "mp3")).lower()
            content_type = OUTPUT_FORMATS.get(output_format, {}).get(
                "content_type",
                "application/octet-stream",
            )

            with open(preview_path, "rb") as file_handle:
                body = file_handle.read()

            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.send_header("Content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == "/":
                self.path = "index.html"
                return http.server.SimpleHTTPRequestHandler.do_GET(self)

            if parsed.path == "/editor":
                self.path = "editor.html"
                return http.server.SimpleHTTPRequestHandler.do_GET(self)

            if parsed.path == "/files":
                files = [
                    file_name
                    for file_name in os.listdir(job_manager.downloads_dir)
                    if not file_name.startswith(".")
                    and os.path.isfile(os.path.join(job_manager.downloads_dir, file_name))
                ]
                files.sort()
                self._send_json(files)
                return

            if parsed.path == "/yt-dlp/update":
                self._send_json(yt_dlp_updater.get_status())
                return

            if parsed.path == "/jobs":
                query = urllib.parse.parse_qs(parsed.query)
                raw_ids = query.get("ids", [])
                ids: list[str] | None = None
                if raw_ids:
                    ids = [job_id for job_id in raw_ids[0].split(",") if job_id]
                self._send_json(job_manager.list_jobs(ids=ids))
                return

            if parsed.path == "/settings":
                self._send_json(job_manager.get_concurrency_settings())
                return

            if parsed.path == "/nas/status":
                self._send_json({"available": nas_client is not None})
                return

            if parsed.path == "/nas/files":
                if nas_client is None:
                    self._send_json({"error": "NAS 未設定"}, status_code=501)
                    return
                try:
                    self._send_json(nas_client.list_files())
                except RuntimeError as exc:
                    print(f"[NAS] list files error: {exc}")
                    self._send_json({"error": str(exc)}, status_code=502)
                except Exception as exc:
                    print(f"[NAS] unexpected list files error: {type(exc).__name__}: {exc}")
                    self._send_json({"error": f"讀取 NAS 檔案失敗：{exc}"}, status_code=502)
                return

            preview_match = re.match(r"^/edits/previews/(?P<preview_id>[^/]+)$", parsed.path)
            if preview_match:
                preview_id = preview_match.group("preview_id")
                preview = edit_manager.get_preview(preview_id)
                if not preview:
                    self._send_json({"error": "找不到預覽"}, status_code=404)
                    return
                self._serve_preview_file(preview)
                return

            if parsed.path.startswith("/downloads/"):
                self.path = parsed.path[1:]
                return http.server.SimpleHTTPRequestHandler.do_GET(self)

            return http.server.SimpleHTTPRequestHandler.do_GET(self)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)

            try:
                data = parse_json_body(self)
            except json.JSONDecodeError:
                self._send_json({"error": "JSON 格式錯誤"}, status_code=400)
                return

            if parsed.path == "/jobs":
                urls = data.get("urls") if isinstance(data, dict) else None
                if not isinstance(urls, list):
                    self._send_json({"error": "urls 必須是陣列"}, status_code=400)
                    return

                created_jobs = job_manager.create_jobs(urls)
                if not created_jobs:
                    self._send_json({"error": "沒有可用的網址"}, status_code=400)
                    return

                self._send_json({"jobs": created_jobs}, status_code=201)
                return

            if parsed.path == "/download":
                url = data.get("url") if isinstance(data, dict) else None
                if not isinstance(url, str):
                    self._send_json({"error": "url is required"}, status_code=400)
                    return

                created_jobs = job_manager.create_jobs([url])
                if not created_jobs:
                    self._send_json({"error": "無效的 URL"}, status_code=400)
                    return

                self._send_json(created_jobs[0], status_code=202)
                return

            if parsed.path == "/yt-dlp/update":
                status_payload = yt_dlp_updater.start_update()
                status_code = 202 if status_payload.get("started") else 200
                self._send_json(status_payload, status_code=status_code)
                return

            if parsed.path == "/settings":
                value = data.get("max_concurrent_jobs") if isinstance(data, dict) else None
                if not isinstance(value, int):
                    self._send_json({"error": "max_concurrent_jobs 必須是整數"}, status_code=400)
                    return
                try:
                    updated = job_manager.set_concurrency_limit(value)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status_code=400)
                    return
                self._send_json(updated, status_code=200)
                return

            if parsed.path == "/edits/preview":
                if not isinstance(data, dict):
                    self._send_json({"error": "JSON 格式錯誤"}, status_code=400)
                    return

                source_file = data.get("source_file")
                delete_ranges = data.get("delete_ranges", [])
                gain_db = data.get("gain_db", 0)
                output_format = data.get("output_format", "mp3")

                if not isinstance(source_file, str):
                    self._send_json({"error": "source_file 必填"}, status_code=400)
                    return
                if not isinstance(gain_db, (int, float)):
                    self._send_json({"error": "gain_db 必須是數字"}, status_code=400)
                    return

                try:
                    created = edit_manager.create_preview(
                        source_file=source_file,
                        delete_ranges=delete_ranges,
                        gain_db=float(gain_db),
                        output_format=str(output_format),
                    )
                except FileNotFoundError as exc:
                    self._send_json({"error": str(exc)}, status_code=404)
                    return
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status_code=400)
                    return
                except RuntimeError as exc:
                    self._send_json({"error": str(exc)}, status_code=500)
                    return

                self._send_json(created, status_code=201)
                return

            if parsed.path == "/edits/commit":
                if not isinstance(data, dict):
                    self._send_json({"error": "JSON 格式錯誤"}, status_code=400)
                    return

                preview_id = data.get("preview_id")
                mode = data.get("mode")
                target_name = data.get("target_name")

                if not isinstance(preview_id, str) or not preview_id.strip():
                    self._send_json({"error": "preview_id 必填"}, status_code=400)
                    return
                if not isinstance(mode, str) or not mode.strip():
                    self._send_json({"error": "mode 必填"}, status_code=400)
                    return
                if target_name is not None and not isinstance(target_name, str):
                    self._send_json({"error": "target_name 必須是字串"}, status_code=400)
                    return

                try:
                    result = edit_manager.commit_preview(
                        preview_id=preview_id,
                        mode=mode,
                        target_name=target_name,
                    )
                except KeyError:
                    self._send_json({"error": "找不到預覽"}, status_code=404)
                    return
                except FileNotFoundError as exc:
                    self._send_json({"error": str(exc)}, status_code=404)
                    return
                except FileExistsError as exc:
                    self._send_json({"error": str(exc)}, status_code=409)
                    return
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status_code=400)
                    return

                self._send_json(result, status_code=200)
                return

            if parsed.path == "/nas/upload":
                if nas_client is None:
                    self._send_json({"error": "NAS 未設定"}, status_code=501)
                    return
                file_name = data.get("file_name") if isinstance(data, dict) else None
                if not isinstance(file_name, str) or not file_name.strip():
                    self._send_json({"error": "file_name 必填"}, status_code=400)
                    return
                file_path = os.path.join(job_manager.downloads_dir, file_name)
                if not os.path.isfile(file_path):
                    self._send_json({"error": "檔案不存在"}, status_code=404)
                    return
                try:
                    result = nas_client.upload(file_path)
                except RuntimeError as exc:
                    print(f"[NAS] upload error: {exc}")
                    self._send_json({"error": str(exc)}, status_code=502)
                    return
                except Exception as exc:
                    print(f"[NAS] unexpected error: {type(exc).__name__}: {exc}")
                    self._send_json({"error": f"上傳失敗：{exc}"}, status_code=502)
                    return
                self._send_json(result, status_code=200)
                return

            retry_match = re.match(r"^/jobs/(?P<job_id>[^/]+)/retry$", parsed.path)
            if retry_match:
                job_id = retry_match.group("job_id")
                try:
                    retried = job_manager.retry_job(job_id)
                except KeyError:
                    self._send_json({"error": "找不到任務"}, status_code=404)
                    return
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status_code=400)
                    return

                self._send_json(retried, status_code=201)
                return

            self._send_json({"error": "Not Found"}, status_code=404)

        def do_DELETE(self):
            parsed = urllib.parse.urlparse(self.path)

            job_match = re.match(r"^/jobs/(?P<job_id>[^/]+)$", parsed.path)
            if job_match:
                job_id = job_match.group("job_id")
                try:
                    deleted = job_manager.delete_job(job_id)
                except KeyError:
                    self._send_json({"error": "找不到任務"}, status_code=404)
                    return
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status_code=409)
                    return

                self._send_json({"deleted": True, "job": deleted}, status_code=200)
                return

            preview_match = re.match(r"^/edits/previews/(?P<preview_id>[^/]+)$", parsed.path)
            if preview_match:
                preview_id = preview_match.group("preview_id")
                deleted = edit_manager.delete_preview(preview_id)
                if not deleted:
                    self._send_json({"error": "找不到預覽"}, status_code=404)
                    return

                self._send_json({"deleted": True}, status_code=200)
                return

            file_match = re.match(r"^/files/(?P<file_name>.+)$", parsed.path)
            if file_match:
                raw_name = urllib.parse.unquote(file_match.group("file_name"))
                try:
                    file_path, safe_name = resolve_file_path(job_manager.downloads_dir, raw_name)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status_code=400)
                    return

                if not os.path.isfile(file_path):
                    self._send_json({"error": "找不到檔案"}, status_code=404)
                    return

                try:
                    os.remove(file_path)
                except OSError as exc:
                    self._send_json({"error": f"刪除失敗：{exc}"}, status_code=500)
                    return

                self._send_json({"deleted": True, "file_name": safe_name}, status_code=200)
                return

            self._send_json({"error": "Not Found"}, status_code=404)

    return MyHttpRequestHandler


class ThreadingHTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def run_server(port: int = PORT) -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv()
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    cookies_file = os.getenv("YTDLP_COOKIES_FILE")
    if not cookies_file:
        default_cookie_path = os.path.join(os.getcwd(), DEFAULT_COOKIES_FILE)
        if os.path.isfile(default_cookie_path):
            cookies_file = default_cookie_path

    job_manager = JobManager(
        downloads_dir=DOWNLOADS_DIR,
        yt_dlp_path="./yt-dlp",
        max_workers=MAX_WORKER_THREADS,
        concurrency_limit=DEFAULT_CONCURRENT_JOBS,
        cookies_file=cookies_file,
        failed_jobs_file=DEFAULT_FAILED_JOBS_FILE,
    )
    edit_manager = EditManager(downloads_dir=DOWNLOADS_DIR)
    yt_dlp_updater = YtDlpUpdater()
    nas_client = NasClient.from_env()
    if nas_client:
        print(f"NAS upload enabled ({nas_client.auth_mode} mode, {nas_client.scheme}) → {nas_client.upload_path}")
    else:
        print("WARNING: NAS upload disabled (need NAS_HOST + NAS_PORT + NAS_UPLOAD_PATH + either NAS_TOKEN or NAS_USER/NAS_PASSWORD)")
    handler = create_request_handler(job_manager, edit_manager, nas_client, yt_dlp_updater)

    try:
        with ThreadingHTTPServer(("", port), handler) as httpd:
            print("serving at port", port)
            httpd.serve_forever()
    finally:
        edit_manager.shutdown()
        job_manager.shutdown()


if __name__ == "__main__":
    run_server()
