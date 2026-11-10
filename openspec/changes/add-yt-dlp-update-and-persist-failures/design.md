## Context

The app is a single Python HTTP server in `server.py` with a browser UI in `index.html`. Download jobs are currently stored in `JobManager` memory only, so restarts discard failed retry targets. Downloads execute `./yt-dlp`, which is a symlink to Homebrew `yt-dlp`; the user confirmed a Homebrew upgrade fixed recent HTTP 403 failures and wants a UI button for the same operation.

## Goals / Non-Goals

**Goals:**

- Provide a web UI button and API endpoint that runs `brew upgrade yt-dlp`.
- Keep updater state visible while the command runs and after it exits.
- Persist failed jobs across restarts while keeping completed and queued history ephemeral.
- Sort failed jobs first in the jobs API response and UI queue.

**Non-Goals:**

- Do not add authentication or localhost-only restrictions for the updater.
- Do not install Homebrew, install `yt-dlp`, or change the configured download command.
- Do not persist successful, queued, downloading, or postprocessing jobs across restarts.

## Decisions

### Persist failed jobs in a local JSON state file

Use a small JSON file under an ignored runtime directory such as `job_state/failed_jobs.json`. `JobManager` loads failed jobs during initialization and writes atomically after failed-job changes. This keeps the implementation dependency-free and matches the app's local-file style.

Alternative considered: persist the full job queue. That would require restart semantics for queued and in-flight jobs and is outside the requested recovery workflow.

### Keep failed ordering server-side

`JobManager.list_jobs()` will return failed jobs first while preserving relative creation order within failed and non-failed groups. This makes the API and UI consistent. The UI can stop reversing the full list when that conflicts with failed-first ordering.

Alternative considered: sort only in JavaScript. That would leave API consumers with different ordering from the visible UI.

### Run brew upgrade through an updater manager

Add a small server-side updater object with status fields, recent output, timestamps, and a single-flight lock. `POST /yt-dlp/update` starts `brew upgrade yt-dlp` in a background thread when idle. `GET /yt-dlp/update` returns current status. Tests inject a fake command runner so they do not invoke Homebrew.

Alternative considered: run the command synchronously inside the request. That risks browser timeouts and blocks the request thread during Homebrew work.

## Risks / Trade-offs

- LAN users can trigger a local package upgrade. This is intentional per user instruction, but the UI must make the action explicit.
- Homebrew output can be long. Store only recent output lines or a bounded text tail in status.
- Atomic JSON writes reduce corruption risk, but abrupt power loss can still lose the latest failed-job update.

## Migration Plan

No data migration is required. On first run after the change, the state directory is created automatically. Existing in-memory failed jobs from before deployment cannot be recovered after a restart because they were never written to disk.

## Open Questions

None.

