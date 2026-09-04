# SubLynt architecture

SubLynt separates subtitle processing from delivery and persistence. The `sublynt_core` package has no FastAPI, SQLAlchemy, or filesystem dependency and can be imported by scripts, workers, or another service.

```text
React UI → versioned FastAPI routes → JobService → SQLite/PostgreSQL metadata
                                      │
                                      ├→ generated-ID disk storage
                                      └→ sublynt_core
                                          parse → analyze → transform → serialize
```

## Processing boundaries

Parsing normalizes UTF-8 BOMs and line endings, recognizes format-specific timing syntax, and produces cues whose timestamps are integer milliseconds. Structural parser findings are carried into analysis. Serialization is format-specific and ends in a normalized newline.

Analysis is read-only. It combines parser findings with configurable timing, reading-speed, line-length, ordering, overlap, duplicate, and identifier rules. Calculations use exact integer duration inputs; floating point is used only for displayed rates.

Transformation clones a document and runs enabled operations in a fixed order: shift, speed scaling, sorting, empty/duplicate removal, clearly invalid timing repair, duration clamping, gap/overlap repair, splitting, merging, renumbering, and conversion. Each mutation records its old and new values. Text splitting prefers sentences, punctuation, then words. It apportions available time by text length and attempts to reserve the minimum duration for every part. If the source duration is insufficient, shorter portions are unavoidable. Merging considers only adjacent short cues with a nonnegative gap and rejects a merge that would exceed duration, line capacity, CPS, or WPM limits.

## Storage and lifecycle

The database contains only job identifiers, display filenames, timestamps, formats, opaque server-generated file paths, and change-log JSON. Subtitle text lives in a dedicated data directory. `JobService` resolves and verifies every stored path is a direct child of that directory. Client filenames are never used as storage paths.

Uploads are decoded strictly as UTF-8, reject NUL bytes, and are bounded before parsing. A generated artifact is serialized and parsed again before it replaces the previous result. DELETE is idempotent. Expired jobs are deleted at API startup, checked hourly while the API runs, and removable by the `sublynt-cleanup` command; production deployments can also schedule that command independently.

The synchronous `JobService` boundary is intentionally narrow. A worker queue can later call the same framework-independent transform functions and update the same job record without moving logic out of route handlers, because route handlers contain orchestration only.
