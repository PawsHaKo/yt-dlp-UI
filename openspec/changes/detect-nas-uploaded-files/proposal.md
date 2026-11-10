## Why

The upload button currently only changes to uploaded after the current browser session successfully uploads a file. After refresh or restart, the UI has no basis for deciding whether a local file already exists on the configured NAS upload path.

## What Changes

- Add a NAS file-listing endpoint that reads the configured `NAS_UPLOAD_PATH` through Synology FileStation and returns existing file names.
- On page load, fetch the NAS file list when NAS upload is configured.
- Mark local files as already uploaded when their file name exactly matches a file name returned from the NAS target folder.
- After a successful upload, add that file name to the browser-side NAS file set so the uploaded state updates immediately.

## Non-Goals

- This change does not compare file size, checksum, metadata, or modified time.
- This change does not recurse into subfolders under `NAS_UPLOAD_PATH`.
- This change does not make NAS listing a high-frequency polling operation.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `nas-file-upload`: NAS upload UI can detect already uploaded files by exact file-name matches against the configured NAS target folder.

## Impact

- Affected specs: nas-file-upload
- Affected code:
  - Modified: server.py
  - Modified: index.html
  - Modified: tests/test_nas_upload.py
  - Modified: tests/test_frontend_ui.py
