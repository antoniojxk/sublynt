Build a complete portfolio-quality web application called **SubLynt**. SubLynt is a subtitle analysis, repair, and conversion utility. Users upload an SRT or WebVTT subtitle file, review detected problems, configure transformations, preview the result, and download a corrected file.

The project should emphasize Python and FastAPI. The React frontend should be polished but deliberately lightweight.

## Primary goals

- Build a working application, not just a scaffold or prototype.
- Keep subtitle-processing logic independent from the web framework.
- Do not use AI services, external datasets, or paid APIs.
- Never execute uploaded content.
- Include meaningful automated tests and clear documentation.
- Favor simple, maintainable architecture over unnecessary abstractions.

## Technology stack

Backend:

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- SQLite for local development, while remaining PostgreSQL-compatible
- Pytest
- Ruff
- Mypy

Frontend:

- React
- TypeScript
- Vite
- A lightweight styling solution such as Tailwind CSS or CSS modules
- TanStack Query if useful
- Vitest for important frontend logic

Infrastructure:

- Dockerfiles for frontend and backend
- Docker Compose for local development
- Environment-variable configuration
- `.env.example`
- GitHub Actions workflow for tests and linting

Inspect the existing repository before making changes. Preserve relevant existing work and follow any repository instructions. Do not stop after creating files: run the application, execute tests, and resolve failures.

## Core user workflow

1. The user uploads an `.srt` or `.vtt` file.
2. The backend validates and parses the file.
3. The application displays:
   - File format
   - Caption count
   - Total duration
   - Average caption duration
   - Average characters per second
   - Average words per minute
   - Number of detected issues
4. The user reviews issues organized by severity and type.
5. The user chooses repair options.
6. The backend generates a transformed version.
7. The user previews before-and-after captions.
8. The user downloads the corrected SRT or WebVTT file.
9. Temporary source and generated files can be deleted manually and are also cleaned up automatically.

## Supported formats

Implement support for:

- SubRip (`.srt`)
- WebVTT (`.vtt`)

Handle:

- UTF-8
- UTF-8 with BOM
- Unix and Windows line endings
- Multiline captions
- Optional WebVTT cue identifiers
- Common WebVTT cue settings

Reject binary files and unsupported encodings with clear, safe error messages.

## Subtitle domain model

The processing engine should use a framework-independent internal model similar to:

- Cue identifier
- Start time
- End time
- Text lines
- Optional cue settings
- Original position
- Validation issues

Represent time internally using integer milliseconds or another exact representation. Do not use floating-point arithmetic for timestamps.

## Analysis rules

Detect at least the following:

- Invalid timestamp syntax
- Missing timestamps
- End time preceding start time
- Negative timestamps
- Empty captions
- Duplicate cue identifiers
- Captions appearing out of chronological order
- Overlapping captions
- Insufficient gaps between captions
- Captions displayed for too little time
- Captions displayed for too long
- Excessive characters per second
- Excessive words per minute
- Too many characters on one line
- Too many lines in one caption
- Duplicate consecutive captions
- Malformed SRT numbering
- Malformed WebVTT headers

Every issue should contain:

- Stable issue code
- Severity: info, warning, or error
- Human-readable explanation
- Cue identifier or index
- Relevant timestamp
- Whether an automatic repair is available

Make analysis thresholds configurable. Provide sensible defaults, including:

- Minimum caption duration
- Maximum caption duration
- Minimum gap
- Maximum characters per second
- Maximum words per minute
- Maximum characters per line
- Maximum lines per caption

## Transformations

Implement these transformations:

- Shift every timestamp forward or backward by a specified number of milliseconds
- Prevent negative timestamps after a shift
- Scale timestamps for playback-speed changes
- Sort cues chronologically
- Renumber SRT cues
- Remove empty cues
- Remove exact duplicate consecutive cues
- Enforce a configurable minimum gap
- Resolve simple overlaps
- Enforce minimum and maximum durations
- Split overly long text cues
- Merge compatible short consecutive cues
- Convert SRT to WebVTT
- Convert WebVTT to SRT

Transformations must be deterministic.

Do not silently make destructive changes. Return a change log describing every modification, including the cue affected, its old value, and its new value.

Provide a conservative “safe repair” preset that only performs low-risk corrections, such as sorting, renumbering, removing empty cues, and correcting clearly invalid timing where possible. More aggressive text splitting, merging, and overlap resolution must be explicitly enabled.

## Splitting and merging behavior

When splitting text:

- Prefer sentence boundaries
- Then prefer punctuation
- Then prefer word boundaries
- Never split in the middle of a word unless absolutely unavoidable
- Divide the available display time proportionally
- Respect minimum caption duration when possible

When merging cues:

- Only merge neighboring cues
- Require a configurable maximum gap
- Do not exceed configured duration, line-count, or reading-speed limits
- Preserve the original text order
- Record the merge in the change log

Document the exact algorithms and trade-offs.

## API design

Create a versioned REST API under `/api/v1`.

Include endpoints equivalent to:

- `GET /health`
- `POST /api/v1/files` — upload and analyze a subtitle file
- `GET /api/v1/files/{file_id}` — return metadata and analysis
- `POST /api/v1/files/{file_id}/transform` — apply selected transformations
- `GET /api/v1/files/{file_id}/preview` — return before-and-after cue data
- `GET /api/v1/files/{file_id}/download` — download the generated file
- `DELETE /api/v1/files/{file_id}` — delete stored source and generated files

You may refine the API if a different design is cleaner, but preserve the complete workflow.

Use consistent response and error models. Include useful OpenAPI descriptions and examples. Validate all transformation settings with Pydantic.

## Processing architecture

Keep the core processing engine separate from FastAPI. Organize it into components such as:

- Parsers
- Serializers
- Validators
- Analyzers
- Transformers
- Report generators

The processing engine should be usable directly from Python without starting the API.

Avoid placing domain logic inside route handlers.

For the MVP, FastAPI background tasks are acceptable. Design the processing boundary so a dedicated worker system could be added later without rewriting the core engine.

## Storage and cleanup

Store only job metadata in the database. Store uploaded and generated files in a dedicated application-data directory.

Requirements:

- Generate server-side file identifiers
- Never trust an uploaded filename as a filesystem path
- Sanitize filenames used in download headers
- Prevent path traversal
- Apply a configurable upload limit, defaulting to 5 MB
- Delete temporary files after a configurable retention period
- Provide a cleanup command or scheduled cleanup function
- Make deletion idempotent
- Do not log subtitle contents

## Frontend

Create a clean, responsive interface with these views:

### Upload

- Drag-and-drop area
- File picker
- Accepted-format information
- Upload progress
- Clear validation errors

### Analysis

- Summary metrics
- Issue counts by severity
- Filterable issue table
- Cue number and timestamp links
- Human-readable explanations

### Repair settings

- Safe-repair preset
- Individual transformation controls
- Advanced thresholds in a collapsible section
- Clear explanation of potentially destructive options

### Preview

- Side-by-side original and transformed cues
- Highlight changed timestamps and text
- Display the change log
- Filter to changed cues only

### Download

- Choose SRT or WebVTT
- Show final validation status
- Download corrected file
- Start over and delete the current job

Do not build a complicated visual subtitle editor or video player for the MVP.

## Accessibility

- Fully keyboard-accessible controls
- Visible focus states
- Proper labels and semantic elements
- Sufficient color contrast
- Do not communicate severity using color alone
- Screen-reader-friendly status and error messages

## Security requirements

- Treat uploaded content strictly as text
- Never execute or render uploaded content as HTML
- Escape subtitle text in the frontend
- Reject files exceeding size and nesting constraints
- Apply request timeouts where appropriate
- Use generated identifiers instead of user-controlled paths
- Configure CORS explicitly
- Avoid exposing internal paths or stack traces
- Add basic rate limiting if it can be implemented cleanly
- Add security-focused tests for path traversal, oversized uploads, malformed files, and HTML-like subtitle text

## Testing

Backend unit tests should cover:

- SRT parsing and serialization
- WebVTT parsing and serialization
- BOM and line-ending handling
- Timestamp conversion
- Malformed timestamps
- Multiline cues
- Overlaps and gaps
- Reading-speed calculations
- Negative shifts
- Playback-speed scaling
- Sorting and renumbering
- Splitting and merging
- Format conversion
- Round-trip stability where applicable
- Security validation

Add API integration tests covering the complete upload, analysis, transformation, preview, download, and deletion workflow.

Include representative subtitle fixtures, but keep them small and original.

Frontend tests should cover important validation and results-rendering behavior. Do not spend excessive effort testing purely decorative presentation.

## Quality expectations

- Use type annotations throughout the Python code
- Keep functions focused and testable
- Provide structured logging without recording subtitle content
- Use consistent API error responses
- Avoid global mutable job state
- Avoid placeholder buttons and unfinished screens
- Remove dead code and generated sample boilerplate
- Make all linters and tests pass
- Verify that downloaded files can be parsed again by the application

## Documentation

Create a thorough README containing:

- What SubLynt does
- Screenshots or a clear interface description
- Architecture overview
- Project structure
- Local setup
- Docker setup
- Environment variables
- API usage examples
- Transformation behavior
- Security considerations
- Current limitations
- Test commands
- Future improvements

Also include a short architecture document explaining how parsing, analysis, transformation, storage, and API layers interact.

## Out of scope for the MVP

Do not implement:

- AI rewriting or translation
- Speech recognition
- Video processing
- Audio synchronization
- User accounts
- Payments
- Cloud storage
- Collaborative editing
- Arbitrary archive uploads

## Acceptance criteria

The project is complete when:

1. `docker compose up --build` starts the frontend and backend.
2. A valid SRT or WebVTT file can be uploaded.
3. The API returns a structured analysis report.
4. The user can configure and apply repairs.
5. The interface shows a before-and-after preview and change log.
6. The corrected file downloads in the selected format.
7. The downloaded file passes the application’s parser and validator.
8. Malformed and oversized files fail safely with clear messages.
9. Backend tests, frontend tests, linting, and type checks pass.
10. The README contains complete run and verification instructions.

Work autonomously through implementation and verification. Make reasonable engineering decisions when details are unspecified. At the end, report what was built, the important design decisions, the commands used to verify it, and any genuine remaining limitations.
