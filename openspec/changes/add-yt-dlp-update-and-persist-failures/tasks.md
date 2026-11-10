## 1. Failed Job Persistence

- [x] 1.1 Add failing tests for Persist failed download jobs using Persist failed jobs in a local JSON state file in `tests/test_server_jobs.py`.
- [x] 1.2 Implement Persist failed download jobs in `server.py`, including startup load and atomic writes to a runtime JSON file.
- [x] 1.3 Add failing tests for Remove recovered failed jobs from persistence when retried jobs complete or failed jobs are deleted.
- [x] 1.4 Implement Remove recovered failed jobs from persistence in retry, completion, and delete flows.
- [x] 1.5 Add failing tests for Failed jobs appear first using Keep failed ordering server-side.
- [x] 1.6 Implement Failed jobs appear first in `JobManager.list_jobs()` and keep the UI from reversing that server order.

## 2. yt-dlp Maintenance

- [x] 2.1 Add failing API tests for Trigger yt-dlp upgrade from the web UI and Prevent concurrent yt-dlp upgrades in `tests/test_server_api.py` using an injected fake updater.
- [x] 2.2 Implement Run brew upgrade through an updater manager in `server.py`, including `POST /yt-dlp/update` and `GET /yt-dlp/update`.
- [x] 2.3 Add failing tests for Report yt-dlp upgrade status after success and failure command exits.
- [x] 2.4 Implement Report yt-dlp upgrade status with bounded command output and timestamps.
- [x] 2.5 Implement Show updater controls in the web UI in `index.html`, including disabled running state and status polling.

## 3. Verification

- [x] 3.1 Run the focused unit and API tests for failed-job persistence and yt-dlp maintenance.
- [x] 3.2 Run the full unittest suite and manually smoke-check the server can start.

