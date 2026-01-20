# STRATA — DC1: Software Artifacts Mining (Data Collection I)

This assignment extends DC0 by implementing full-history mining of Git repositories.  
The goal is to collect commits, parent relationships, per-commit stats, per-file changes, and provenance information, while ensuring the pipeline is idempotent, reproducible, and test-driven.

---

## What Was Implemented

For DC1, the miner:

- Traverses the full commit history (oldest → newest)
- Stores commit metadata
- Stores parent relationships
- Stores aggregate commit stats
- Stores per-file change stats
- Records provenance in `run_log`
- Enforces idempotent behavior (no duplicates on re-run)
- Validates invariants programmatically

All behavior is verified using pytest.

---

## Commands

Initialize schema:

```bash
python -c "from src import db_utils; db_utils.exec_sql_file('data/schema.sql')"
