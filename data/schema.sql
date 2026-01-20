-- Drop existing tables to ensure a clean schema
DROP TABLE IF EXISTS run_log CASCADE;
DROP TABLE IF EXISTS commit_parents CASCADE;
DROP TABLE IF EXISTS commit_files CASCADE;
DROP TABLE IF EXISTS commit_stats CASCADE;
DROP TABLE IF EXISTS commits CASCADE;

CREATE TABLE IF NOT EXISTS commits (
    id SERIAL PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    author_name TEXT NOT NULL,
    message TEXT NOT NULL,
    commit_ts TIMESTAMP NOT NULL
);
-- Ensure no duplicate commits by hash
CREATE UNIQUE INDEX IF NOT EXISTS idx_commits_hash ON commits(commit_hash);

-- Per-commit aggregate stats
CREATE TABLE IF NOT EXISTS commit_stats (
    commit_id INTEGER PRIMARY KEY REFERENCES commits(id) ON DELETE CASCADE,
    files_changed INTEGER NOT NULL,
    insertions INTEGER NOT NULL,
    deletions INTEGER NOT NULL
);

-- Per-file change details for each commit
CREATE TABLE IF NOT EXISTS commit_files (
    id SERIAL PRIMARY KEY,
    commit_id INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    change_type TEXT NOT NULL,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0
);
-- Ensure idempotent inserts per (commit_id, file_path)
CREATE UNIQUE INDEX IF NOT EXISTS uq_commit_files_commit_path ON commit_files(commit_id, file_path);

-- Parent relationships
CREATE TABLE IF NOT EXISTS commit_parents (
    commit_id INTEGER NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    parent_hash TEXT NOT NULL,
    PRIMARY KEY (commit_id, parent_hash)
);

-- Provenance logging
CREATE TABLE IF NOT EXISTS run_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    repo_path TEXT NOT NULL,
    head_hash TEXT NOT NULL,
    commit_count INTEGER NOT NULL
);
