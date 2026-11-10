## ADDED Requirements

### Requirement: Trigger yt-dlp upgrade from the web UI

The system SHALL provide a web-accessible action that starts a Homebrew upgrade for the application yt-dlp executable.

#### Scenario: Start upgrade

- **WHEN** a user requests a yt-dlp upgrade from the web UI
- **THEN** the server SHALL start the configured update command in the background
- **THEN** the response SHALL include an update status payload

### Requirement: Prevent concurrent yt-dlp upgrades

The system SHALL allow at most one yt-dlp upgrade process to run at a time.

#### Scenario: Upgrade already running

- **WHEN** a yt-dlp upgrade is already running
- **THEN** a second upgrade request SHALL NOT start another process
- **THEN** the response SHALL report the existing running status

### Requirement: Report yt-dlp upgrade status

The system SHALL expose the current yt-dlp upgrade status to the web UI.

#### Scenario: Status after command exits

- **WHEN** the update command exits
- **THEN** the status response SHALL include whether the command succeeded or failed
- **THEN** the status response SHALL include recent command output for user diagnosis

### Requirement: Show updater controls in the web UI

The web UI SHALL provide a visible control for triggering yt-dlp updates and showing update progress or result.

#### Scenario: User triggers update button

- **WHEN** the user clicks the update control
- **THEN** the UI SHALL disable duplicate submissions while the update is running
- **THEN** the UI SHALL show the latest update status returned by the server

