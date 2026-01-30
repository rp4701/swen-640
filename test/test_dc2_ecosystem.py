import os
from datetime import datetime, timezone, timedelta
from git import Repo

from src.git_miner import (
    ingest_issues,
    ingest_pull_requests,
    ingest_ci,
    mine_history,
    validate_invariants,
)
from src import db_utils



# Helpers


def seed_two_commit_repo(tmp_path):
    repo = Repo.init(tmp_path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", "DC2 Tester")
        cw.set_value("user", "email", "dc2@test.com")

    f = tmp_path / "hello.txt"
    f.write_text("hello\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Initial commit")

    f.write_text("hello\nworld\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Second commit")

    return repo



# A. Issues + PRs ingestion (idempotent)


def test_issues_and_prs_upsert_idempotent():
    provider = "github"
    repo = "acme/widgets"

    issues = [
        {
            "number": 1,
            "title": "Open issue",
            "author": "alice",
            "state": "open",
            "created_at": "2024-01-01T10:00:00Z",
            "closed_at": None,
        },
        {
            "number": 2,
            "title": "Closed issue",
            "author": "bob",
            "state": "closed",
            "created_at": "2024-01-02T10:00:00Z",
            "closed_at": "2024-01-03T10:00:00Z",
        },
    ]

    prs = [
        {
            "number": 10,
            "title": "Open PR",
            "author": "carol",
            "state": "open",
            "created_at": "2024-01-05T12:00:00Z",
            "merged_at": None,
            "closed_at": None,
        },
        {
            "number": 11,
            "title": "Merged PR",
            "author": "dave",
            "state": "closed",  # provider lies
            "created_at": "2024-01-06T12:00:00Z",
            "merged_at": "2024-01-07T12:00:00Z",
            "closed_at": "2024-01-07T12:00:00Z",
        },
    ]

    ingest_issues(provider, repo, issues)
    ingest_pull_requests(provider, repo, prs)

    # Replay (idempotency)
    ingest_issues(provider, repo, issues)
    ingest_pull_requests(provider, repo, prs)

    assert db_utils.exec_get_one("SELECT COUNT(*) FROM issues;")[0] == 2
    assert db_utils.exec_get_one("SELECT COUNT(*) FROM pull_requests;")[0] == 2

    merged_state = db_utils.exec_get_one(
        "SELECT state FROM pull_requests WHERE pr_number = 11;"
    )[0]
    assert merged_state == "merged"



# B. CI pipelines + jobs ingestion


def test_ci_pipelines_and_jobs(tmp_path):
    repo = seed_two_commit_repo(tmp_path)
    mine_history(str(tmp_path))

    head_sha = repo.head.commit.hexsha
    t0 = datetime.now(timezone.utc)

    pipelines = [
        {
            "pipeline_id": "1001",
            "status": "success",
            "created_at": t0.isoformat(),
            "updated_at": (t0 + timedelta(minutes=5)).isoformat(),
            "sha": head_sha,
        }
    ]

    jobs = {
        "1001": [
            {
                "pipeline_id": "1001",
                "job_id": "2001",
                "name": "build",
                "status": "success",
                "started_at": t0.isoformat(),
                "finished_at": (t0 + timedelta(minutes=2)).isoformat(),
                "duration_seconds": 120,
            },
            {
                "pipeline_id": "1001",
                "job_id": "2002",
                "name": "test",
                "status": "success",
                "started_at": (t0 + timedelta(minutes=2)).isoformat(),
                "finished_at": (t0 + timedelta(minutes=5)).isoformat(),
                "duration_seconds": 180,
            },
        ]
    }

    ingest_ci("github", "acme/widgets", pipelines, jobs)

    # Replay
    ingest_ci("github", "acme/widgets", pipelines, jobs)

    assert db_utils.exec_get_one("SELECT COUNT(*) FROM ci_pipelines;")[0] == 1
    assert db_utils.exec_get_one("SELECT COUNT(*) FROM ci_jobs;")[0] == 2



# C. CI SHA matches mined commit


def test_ci_sha_matches_commit(tmp_path):
    repo = seed_two_commit_repo(tmp_path)
    mine_history(str(tmp_path))

    sha = repo.head.commit.hexsha

    pipelines = [
        {
            "pipeline_id": "42",
            "status": "success",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:05:00Z",
            "sha": sha,
        }
    ]

    ingest_ci("github", "acme/widgets", pipelines)

    exists = db_utils.exec_get_one(
        "SELECT 1 FROM commits WHERE commit_hash = %s;", (sha,)
    )
    assert exists is not None



# D. Timestamp 


def test_timestamp_formats_are_accepted():
    ingest_issues(
        "github",
        "acme/widgets",
        [
            {
                "number": 99,
                "title": "Timestamp test",
                "author": "tester",
                "state": "open",
                "created_at": "2024-01-01 12:00:00",
                "closed_at": None,
            }
        ],
    )

    ts = db_utils.exec_get_one(
        "SELECT created_at FROM issues WHERE issue_number = 99;"
    )[0]
    assert ts.tzinfo is not None



# E. Validation invariants still hold


def test_validate_invariants_still_hold():
    n_commits, n_stats, n_orphans = validate_invariants()
    assert n_stats == n_commits
    assert n_orphans == 0
