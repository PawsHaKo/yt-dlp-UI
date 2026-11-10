## ADDED Requirements

### Requirement: NAS target folder file names are available to the UI
The system SHALL provide a read-only endpoint that returns the file names currently present in the configured NAS upload folder.

#### Scenario: NAS is configured and listing succeeds
- **WHEN** the browser requests the NAS file list
- **THEN** the system SHALL query the configured `NAS_UPLOAD_PATH` with the Synology FileStation List API
- **THEN** the system SHALL return a JSON array containing non-directory file names from that folder

#### Scenario: NAS listing fails
- **WHEN** the NAS FileStation List API fails or cannot be reached
- **THEN** the system SHALL return HTTP 502 with a structured JSON error

#### Scenario: NAS is not configured
- **WHEN** the browser requests the NAS file list and NAS settings are unavailable
- **THEN** the system SHALL return HTTP 501 with a structured JSON error

### Requirement: UI marks local files already present on NAS
The system SHALL compare local download file names against the NAS target folder file names and display matching local files as already uploaded.

#### Scenario: Local file name exists on NAS
- **WHEN** the page loads and the NAS file list contains a file name that exactly matches a local download file name
- **THEN** the matching local file's NAS upload button SHALL display the uploaded success state
- **THEN** the matching local file's NAS upload button SHALL be disabled

##### Example:
- **GIVEN** the local download list contains `song.mp3`
- **AND** the NAS file list contains `song.mp3`
- **WHEN** the file list renders
- **THEN** the `song.mp3` NAS button displays `✓ 已上傳`
- **AND** the `song.mp3` NAS button is disabled

#### Scenario: NAS file list is unavailable
- **WHEN** the page loads and the NAS file list request fails
- **THEN** the UI SHALL NOT mark local files as uploaded based on NAS state
- **THEN** the UI SHALL keep NAS upload buttons available for local files

##### Example:
- **GIVEN** the local download list contains `song.mp3`
- **AND** the NAS file list request returns HTTP 502
- **WHEN** the file list renders
- **THEN** the `song.mp3` NAS button displays `傳到 NAS`
- **AND** the `song.mp3` NAS button is enabled

#### Scenario: Upload succeeds after page load
- **WHEN** a local file is uploaded successfully to the NAS
- **THEN** the UI SHALL add that file name to its NAS file-name cache
- **THEN** the UI SHALL display that file as uploaded without requiring a page refresh

##### Example:
- **GIVEN** the local download list contains `song.mp3`
- **WHEN** uploading `song.mp3` returns HTTP 200
- **THEN** the UI stores `song.mp3` in the NAS file-name cache
- **AND** the `song.mp3` NAS button displays `✓ 已上傳`
