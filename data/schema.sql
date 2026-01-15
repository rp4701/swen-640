-- STRATA DC0 schema
DROP TABLE IF EXISTS commits CASCADE;
CREATE TABLE IF NOT EXISTS commits (
    id SERIAL PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    author_name TEXT NOT NULL,
    message TEXT NOT NULL,
    commit_ts TIMESTAMP NOT NULL
);
