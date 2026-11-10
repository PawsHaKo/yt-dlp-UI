## 1. NAS File Listing

- [x] 1.1 Add failing tests for "NAS target folder file names are available to the UI" in `tests/test_nas_upload.py`, covering the NAS Listing API success path and `GET /nas/files` endpoint.
- [x] 1.2 Implement "NAS target folder file names are available to the UI" in `server.py`, including the NAS Listing API, FileStation List API parsing, and endpoint error handling.

## 2. Uploaded-State UI

- [x] 2.1 Add failing frontend tests for "UI marks local files already present on NAS" in `tests/test_frontend_ui.py`, covering filename matching and refresh scope.
- [x] 2.2 Implement "UI marks local files already present on NAS" in `index.html`, including browser-side filename matching, refresh scope, NAS file-name cache, and uploaded button rendering.

## 3. Verification

- [x] 3.1 Run focused NAS and frontend tests.
- [x] 3.2 Run the full unittest suite.
