# post-download-audio-editing Specification

## Purpose

TBD - created by archiving change 'add-post-download-audio-editor'. Update Purpose after archive.

## Requirements

### Requirement: Users can enter an audio editor from downloaded files
The system SHALL provide an edit entry for each downloadable audio file and SHALL open a dedicated editor view for the selected file.

#### Scenario: Open editor from file list
- **WHEN** a user selects Edit on an existing downloaded file
- **THEN** the system opens the editor view bound to that exact file


<!-- @trace
source: add-post-download-audio-editor
updated: 2026-03-23
code:
  - README.md
  - .agents/skills/spectra-ask/SKILL.md
  - .agents/skills/spectra-archive/SKILL.md
  - .agents/skills/spectra-debug/SKILL.md
  - editor.html
  - AGENTS.md
  - .agents/skills/spectra-audit/SKILL.md
  - .agents/skills/spectra-apply/SKILL.md
  - index.html
  - .DS_Store
  - pyproject.toml
  - .agents/skills/spectra-discuss/SKILL.md
  - main.py
  - __pycache__/server.cpython-314.pyc
  - .agents/skills/spectra-ingest/SKILL.md
  - server.py
  - .agents/skills/spectra-propose/SKILL.md
  - .python-version
  - uv.lock
tests:
  - tests/__pycache__/test_server_jobs.cpython-314.pyc
  - tests/test_server_api.py
  - tests/test_server_jobs.py
  - tests/__pycache__/test_server_api.cpython-314.pyc
-->

---
### Requirement: Editor SHALL support waveform-based multi-range deletion and gain control
The editor SHALL render an interactive waveform with timeline and zoom, SHALL allow creating multiple deletion ranges, SHALL allow removing a range, SHALL allow clearing all ranges, and SHALL allow whole-track gain control from -20 dB to +20 dB.

#### Scenario: Configure edit operations
- **WHEN** a user adds two deletion ranges and sets gain to +3 dB
- **THEN** the editor state stores both ranges and the selected gain value for preview generation


<!-- @trace
source: add-post-download-audio-editor
updated: 2026-03-23
code:
  - README.md
  - .agents/skills/spectra-ask/SKILL.md
  - .agents/skills/spectra-archive/SKILL.md
  - .agents/skills/spectra-debug/SKILL.md
  - editor.html
  - AGENTS.md
  - .agents/skills/spectra-audit/SKILL.md
  - .agents/skills/spectra-apply/SKILL.md
  - index.html
  - .DS_Store
  - pyproject.toml
  - .agents/skills/spectra-discuss/SKILL.md
  - main.py
  - __pycache__/server.cpython-314.pyc
  - .agents/skills/spectra-ingest/SKILL.md
  - server.py
  - .agents/skills/spectra-propose/SKILL.md
  - .python-version
  - uv.lock
tests:
  - tests/__pycache__/test_server_jobs.cpython-314.pyc
  - tests/test_server_api.py
  - tests/test_server_jobs.py
  - tests/__pycache__/test_server_api.cpython-314.pyc
-->

---
### Requirement: System SHALL generate preview audio on demand
The system SHALL generate a server-side preview file only when the user requests preview refresh and SHALL return a preview identifier and playable preview URL.

#### Scenario: Refresh preview
- **WHEN** a user clicks Update Preview with valid ranges and output format
- **THEN** the system creates a preview artifact and returns a preview_id and preview URL


<!-- @trace
source: add-post-download-audio-editor
updated: 2026-03-23
code:
  - README.md
  - .agents/skills/spectra-ask/SKILL.md
  - .agents/skills/spectra-archive/SKILL.md
  - .agents/skills/spectra-debug/SKILL.md
  - editor.html
  - AGENTS.md
  - .agents/skills/spectra-audit/SKILL.md
  - .agents/skills/spectra-apply/SKILL.md
  - index.html
  - .DS_Store
  - pyproject.toml
  - .agents/skills/spectra-discuss/SKILL.md
  - main.py
  - __pycache__/server.cpython-314.pyc
  - .agents/skills/spectra-ingest/SKILL.md
  - server.py
  - .agents/skills/spectra-propose/SKILL.md
  - .python-version
  - uv.lock
tests:
  - tests/__pycache__/test_server_jobs.cpython-314.pyc
  - tests/test_server_api.py
  - tests/test_server_jobs.py
  - tests/__pycache__/test_server_api.cpython-314.pyc
-->

---
### Requirement: System SHALL support save-as and overwrite commit modes
The system SHALL allow committing an approved preview as save-as or overwrite. In overwrite mode, the system MUST enforce same format as source and MUST create a backup before replacing the original file.

#### Scenario: Save as new file
- **WHEN** a user commits with mode save_as
- **THEN** the system writes a new output file and keeps the source file unchanged

#### Scenario: Overwrite with backup
- **WHEN** a user commits with mode overwrite and matching format
- **THEN** the system creates a timestamped backup and replaces the source file with the committed output

#### Scenario: Reject overwrite on format mismatch
- **WHEN** a user commits with mode overwrite and a different output format from source
- **THEN** the system rejects the request with a client error


<!-- @trace
source: add-post-download-audio-editor
updated: 2026-03-23
code:
  - README.md
  - .agents/skills/spectra-ask/SKILL.md
  - .agents/skills/spectra-archive/SKILL.md
  - .agents/skills/spectra-debug/SKILL.md
  - editor.html
  - AGENTS.md
  - .agents/skills/spectra-audit/SKILL.md
  - .agents/skills/spectra-apply/SKILL.md
  - index.html
  - .DS_Store
  - pyproject.toml
  - .agents/skills/spectra-discuss/SKILL.md
  - main.py
  - __pycache__/server.cpython-314.pyc
  - .agents/skills/spectra-ingest/SKILL.md
  - server.py
  - .agents/skills/spectra-propose/SKILL.md
  - .python-version
  - uv.lock
tests:
  - tests/__pycache__/test_server_jobs.cpython-314.pyc
  - tests/test_server_api.py
  - tests/test_server_jobs.py
  - tests/__pycache__/test_server_api.cpython-314.pyc
-->

---
### Requirement: System SHALL manage preview temp lifecycle
The system SHALL delete preview temp files immediately after cancel or commit and SHALL run periodic cleanup for expired preview artifacts.

#### Scenario: Cleanup on cancel
- **WHEN** a user cancels an active preview session
- **THEN** the associated preview temp file is deleted

#### Scenario: Cleanup expired temp files
- **WHEN** the scheduled cleanup job runs
- **THEN** preview temp files older than the configured TTL are removed

<!-- @trace
source: add-post-download-audio-editor
updated: 2026-03-23
code:
  - README.md
  - .agents/skills/spectra-ask/SKILL.md
  - .agents/skills/spectra-archive/SKILL.md
  - .agents/skills/spectra-debug/SKILL.md
  - editor.html
  - AGENTS.md
  - .agents/skills/spectra-audit/SKILL.md
  - .agents/skills/spectra-apply/SKILL.md
  - index.html
  - .DS_Store
  - pyproject.toml
  - .agents/skills/spectra-discuss/SKILL.md
  - main.py
  - __pycache__/server.cpython-314.pyc
  - .agents/skills/spectra-ingest/SKILL.md
  - server.py
  - .agents/skills/spectra-propose/SKILL.md
  - .python-version
  - uv.lock
tests:
  - tests/__pycache__/test_server_jobs.cpython-314.pyc
  - tests/test_server_api.py
  - tests/test_server_jobs.py
  - tests/__pycache__/test_server_api.cpython-314.pyc
-->