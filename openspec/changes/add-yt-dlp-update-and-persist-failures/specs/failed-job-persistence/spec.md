## ADDED Requirements

### Requirement: Persist failed download jobs

The system SHALL persist failed download jobs to disk so they remain available after the service restarts.

#### Scenario: Failed job survives restart

- **GIVEN** a download job has status failed
- **WHEN** the service starts again
- **THEN** the failed job SHALL appear in the jobs list with its URL, error, and failed status preserved

### Requirement: Remove recovered failed jobs from persistence

The system SHALL remove a persisted failed job when that job no longer needs retry attention.

#### Scenario: Retried job completes successfully

- **GIVEN** a failed job was persisted
- **WHEN** the job is retried and completes successfully
- **THEN** the job SHALL be removed from failed-job persistence

#### Scenario: Failed job is deleted

- **GIVEN** a failed job was persisted
- **WHEN** the user deletes the job
- **THEN** the job SHALL be removed from failed-job persistence

### Requirement: Failed jobs appear first

The system SHALL order failed jobs before other jobs in the jobs API response and queue display.

#### Scenario: Mixed job statuses

- **GIVEN** jobs with failed, queued, downloading, completed, and postprocessing statuses exist
- **WHEN** the jobs list is requested
- **THEN** failed jobs SHALL appear before non-failed jobs

##### Example: failed jobs sorted first

- **GIVEN** jobs in creation order: A(completed), B(failed), C(queued), D(failed)
- **WHEN** the jobs list is requested
- **THEN** jobs appear in order: B, D, A, C

