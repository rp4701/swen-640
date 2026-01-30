# STRATA — DC2: Ecosystem Artifacts (Data Collection II)

This assignment builds on DC1 by extending the mining pipeline to collect
ecosystem-level artifacts such as issues, pull/merge requests, and CI
pipelines/jobs, while keeping all DC1 behavior intact.

The focus is on provider-agnostic ingestion, idempotent ETL, and
reproducible, test-driven data collection.

---

## DC1 Continuity

All DC1 functionality remains unchanged and continues to pass:

- Full commit history mining (oldest → newest)
- Commit metadata storage
- Parent relationships
- Aggregate commit stats
- Per-file change stats
- Provenance tracking via `run_log`
- Idempotent re-runs
- Programmatic invariant validation

---

## New Functions (DC2)

The miner was extended with provider-agnostic ingestion helpers:

- `ingest_issues` / `upsert_issue`
- `ingest_pull_requests` / `upsert_pull_request`
- `ingest_ci`
- `upsert_ci_pipeline`
- `upsert_ci_job`
- `_normalize_timestamp_to_utc` for consistent TIMESTAMPTZ handling

All inserts use composite unique keys and conflict-aware upserts to ensure
safe re-runs.

---

## New Tests (DC2)

The following tests were added:

- Issues and pull requests ingestion with idempotent replays
- Pull request state normalization (`merged` vs `closed`)
- CI pipelines and jobs ingestion with replay safety
- CI pipeline SHA validation against mined commits
- Timestamp coercion for multiple ISO8601 formats
- Validation invariants (no orphan parents, stats aligned with commits)

All tests are deterministic and network-free.

---

## Commands

Initialize schema:
```bash
python -c "from src import db_utils; db_utils.exec_sql_file('data/schema.sql')"
