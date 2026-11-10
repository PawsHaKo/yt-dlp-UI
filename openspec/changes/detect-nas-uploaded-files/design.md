## Context

The existing NAS integration already authenticates against Synology FileStation and uploads files to `NAS_UPLOAD_PATH`. The missing piece is a read-only view of the same folder, so the browser can determine whether a local file has already been uploaded after page reloads or service restarts.

## Decisions

### NAS Listing API

- Add `GET /nas/files`.
- Return HTTP 501 with JSON error when NAS is not configured, matching the upload endpoint behavior.
- Use `SYNO.FileStation.List` against `NAS_UPLOAD_PATH`.
- Return a JSON array of exact file names for non-directory entries only.
- Propagate NAS listing failures as HTTP 502 with a JSON error message.

### Filename Matching

- The browser stores returned NAS file names in a `Set`.
- `renderFileList()` checks each local file name against that set.
- Exact matches display the same uploaded success state as a completed upload and disable the NAS upload button.
- If NAS listing fails, the browser does not infer uploaded state from stale or partial data; upload buttons remain available.

### Refresh Scope

- NAS file listing runs on initial page load when NAS is configured.
- A successful upload adds that file name to the local `Set` immediately.
- The existing frequent local file refresh does not call NAS listing every time, avoiding repeated NAS logins and unnecessary network load.

## Risks

- Exact file-name matching can produce false positives when different content shares the same name. This is accepted by the user for this workflow.
- Files added to the NAS from another device after page load will not be detected until the page reloads.
