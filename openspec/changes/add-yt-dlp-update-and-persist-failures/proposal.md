## Why

YouTube download failures can often be resolved by upgrading the Homebrew-installed `yt-dlp`, but doing that from a terminal interrupts the browser-based workflow. Failed jobs are currently kept only in memory, so restarting the service loses the retry list and makes failed downloads harder to recover.

## What Changes

- Add a LAN-accessible web action that runs `brew upgrade yt-dlp` from the UI and exposes update status to the browser.
- Persist failed download jobs to disk so they reappear after service restart.
- Keep failed jobs prominent by ordering them before non-failed jobs in the queue/API view.
- Remove a persisted failure when that job is retried and later completes successfully or when the job is deleted.

## Non-Goals

- This change does not add authentication or restrict the update button to localhost; anyone who can access the web UI may trigger it.
- This change does not install Homebrew or `yt-dlp` if they are missing.
- This change does not persist completed or queued job history across restarts.

## Capabilities

### New Capabilities

- `yt-dlp-maintenance`: UI and API support for triggering and observing a `yt-dlp` Homebrew upgrade.
- `failed-job-persistence`: Persisting failed download jobs across service restarts and ordering failed jobs prominently.

### Modified Capabilities

(none)

## Impact

- Affected code:
  - Modified: server.py
  - Modified: index.html
  - Modified: tests/test_server_jobs.py
  - Modified: tests/test_server_api.py
  - New: runtime job state directory created by the application

