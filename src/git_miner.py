from datetime import datetime
from typing import Optional, Iterable, Tuple
from git import Repo
from . import db_utils


def upsert_commit(repo_commit) -> int:
    data = {
        "hash": repo_commit.hexsha,
        "author_name": repo_commit.author.name if repo_commit.author else None,
        "message": repo_commit.message,
        "commit_ts": repo_commit.committed_datetime,
    }

    # Insert if missing (commit happens here)
    db_utils.exec_commit(
        """
        INSERT INTO commits (commit_hash, author_name, message, commit_ts)
        VALUES (%(hash)s, %(author_name)s, %(message)s, %(commit_ts)s)
        ON CONFLICT (commit_hash) DO NOTHING;
        """,
        data,
    )

    # Always fetch the id after
    row = db_utils.exec_get_one(
        "SELECT id FROM commits WHERE commit_hash = %(hash)s;",
        {"hash": data["hash"]},
    )
    return row[0]


def insert_parents(commit_id: int, parents: Iterable[str]) -> None:
    for p in parents:
        db_utils.exec_commit(
            """
            INSERT INTO commit_parents (commit_id, parent_hash)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (commit_id, p),
        )


def insert_stats(commit_id: int, repo_commit) -> None:
    total = getattr(repo_commit.stats, "total", {}) or {}

    files_changed = int(total.get("files", 0))
    insertions = int(total.get("insertions", 0))
    deletions = int(total.get("deletions", 0))

    db_utils.exec_commit(
        """
        INSERT INTO commit_stats (commit_id, files_changed, insertions, deletions)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (commit_id) DO NOTHING;
        """,
        (commit_id, files_changed, insertions, deletions),
    )


def insert_files(commit_id: int, repo_commit) -> None:
    files = getattr(repo_commit.stats, "files", {}) or {}

    change_types = {}

    try:
        parent = repo_commit.parents[0] if repo_commit.parents else None
        if parent is not None:
            for diff in parent.diff(repo_commit):
                path = diff.b_path or diff.a_path
                if path:
                    change_types[path] = diff.change_type.upper()
        else:
            for path in files.keys():
                change_types[path] = "A"
    except Exception:
        pass

    for path, data in files.items():
        additions = int(data.get("insertions", 0))
        deletions = int(data.get("deletions", 0))
        change_type = change_types.get(path, "M")

        db_utils.exec_commit(
            """
            INSERT INTO commit_files
              (commit_id, file_path, change_type, additions, deletions)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (commit_id, file_path) DO NOTHING;
            """,
            (commit_id, path, change_type, additions, deletions),
        )


def insert_run_log(repo_path: str, head_hash: str, commit_count: int) -> None:
    db_utils.exec_commit(
        """
        INSERT INTO run_log (repo_path, head_hash, commit_count)
        VALUES (%s, %s, %s);
        """,
        (repo_path, head_hash, commit_count),
    )


def validate_invariants() -> Tuple[int, int, int]:
    n_commits = db_utils.exec_get_one("SELECT COUNT(*) FROM commits;")[0]
    n_stats = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_stats;")[0]

    n_orphan_parents = db_utils.exec_get_one(
        """
        SELECT COUNT(*)
        FROM commit_parents cp
        WHERE NOT EXISTS (
            SELECT 1 FROM commits c
            WHERE c.commit_hash = cp.parent_hash
        );
        """
    )[0]

    return (n_commits, n_stats, n_orphan_parents)


def mine_history(repo_path: str = ".", max_commits: Optional[int] = None, record_run: bool = True) -> int:
    with Repo(repo_path) as repo:
        commits = list(repo.iter_commits("HEAD"))
        commits.reverse()
        count = 0
        for c in commits:
            cid = upsert_commit(c)
            insert_parents(cid, [p.hexsha for p in c.parents])
            insert_stats(cid, c)
            insert_files(cid, c)
            count += 1
            if max_commits is not None and count >= max_commits:
                break
        if record_run:
            head_hash = repo.head.commit.hexsha
            insert_run_log(repo_path, head_hash, count)
        return count


def mine_and_store(repo_path: str = ".", max_commits: Optional[int] = None):
    mine_history(repo_path=repo_path, max_commits=max_commits, record_run=True)

    row = db_utils.exec_get_one(
        """
        SELECT commit_hash, author_name, message
        FROM commits
        ORDER BY id DESC
        LIMIT 1;
        """
    )

    return {
        "hash": row[0],
        "author_name": row[1],
        "message": row[2],
    }

# DC2: Ecosystem Artifacts


from datetime import datetime, timezone
from typing import Dict, Any, Optional, Iterable


def _normalize_timestamp_to_utc(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    v = str(value)

    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        raise ValueError(f"Unrecognized timestamp: {value}")


# ---- Issues ----

def upsert_issue(provider: str, repo: str, issue: Dict[str, Any]) -> int:
    rows = db_utils.exec_commit_returning(
        """
        INSERT INTO issues
          (provider, repo, issue_number, title, author, state, created_at, closed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (provider, repo, issue_number) DO UPDATE SET
          title = EXCLUDED.title,
          state = EXCLUDED.state,
          author = COALESCE(EXCLUDED.author, issues.author),
          created_at = LEAST(issues.created_at, EXCLUDED.created_at),
          closed_at = COALESCE(EXCLUDED.closed_at, issues.closed_at)
        RETURNING id;
        """,
        (
            provider,
            repo,
            issue["number"],
            issue["title"],
            issue.get("author"),
            issue["state"],
            _normalize_timestamp_to_utc(issue["created_at"]),
            _normalize_timestamp_to_utc(issue.get("closed_at")),
        ),
    )
    return rows[0][0]


def ingest_issues(provider: str, repo: str, issues: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for issue in issues:
        upsert_issue(provider, repo, issue)
        count += 1
    return count


# ---- Pull Requests ----

def upsert_pull_request(provider: str, repo: str, pr: Dict[str, Any]) -> int:
    state = "merged" if pr.get("merged_at") else pr.get("state", "open")

    rows = db_utils.exec_commit_returning(
        """
        INSERT INTO pull_requests
          (provider, repo, pr_number, title, author, state,
           created_at, merged_at, closed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (provider, repo, pr_number) DO UPDATE SET
          title = EXCLUDED.title,
          state = EXCLUDED.state,
          author = COALESCE(EXCLUDED.author, pull_requests.author),
          created_at = LEAST(pull_requests.created_at, EXCLUDED.created_at),
          merged_at = COALESCE(EXCLUDED.merged_at, pull_requests.merged_at),
          closed_at = COALESCE(EXCLUDED.closed_at, pull_requests.closed_at)
        RETURNING id;
        """,
        (
            provider,
            repo,
            pr["number"],
            pr["title"],
            pr.get("author"),
            state,
            _normalize_timestamp_to_utc(pr["created_at"]),
            _normalize_timestamp_to_utc(pr.get("merged_at")),
            _normalize_timestamp_to_utc(pr.get("closed_at")),
        ),
    )
    return rows[0][0]


def ingest_pull_requests(provider: str, repo: str, prs: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for pr in prs:
        upsert_pull_request(provider, repo, pr)
        count += 1
    return count


# ---- CI Pipelines & Jobs ----

def upsert_ci_pipeline(provider: str, repo: str, pipe: Dict[str, Any]) -> int:
    rows = db_utils.exec_commit_returning(
        """
        INSERT INTO ci_pipelines
          (provider, repo, pipeline_id, status, created_at, updated_at, sha)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (provider, repo, pipeline_id) DO UPDATE SET
          status = EXCLUDED.status,
          created_at = LEAST(ci_pipelines.created_at, EXCLUDED.created_at),
          updated_at = COALESCE(EXCLUDED.updated_at, ci_pipelines.updated_at),
          sha = COALESCE(EXCLUDED.sha, ci_pipelines.sha)
        RETURNING id;
        """,
        (
            provider,
            repo,
            str(pipe["pipeline_id"]),
            pipe["status"],
            _normalize_timestamp_to_utc(pipe["created_at"]),
            _normalize_timestamp_to_utc(pipe.get("updated_at")),
            pipe.get("sha"),
        ),
    )
    return rows[0][0]


def upsert_ci_job(provider: str, repo: str, job: Dict[str, Any]) -> int:
    rows = db_utils.exec_commit_returning(
        """
        INSERT INTO ci_jobs
          (provider, repo, pipeline_id, job_id, name, status,
           started_at, finished_at, duration_seconds)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (provider, repo, job_id) DO UPDATE SET
          status = COALESCE(EXCLUDED.status, ci_jobs.status),
          name = COALESCE(EXCLUDED.name, ci_jobs.name),
          started_at = COALESCE(EXCLUDED.started_at, ci_jobs.started_at),
          finished_at = COALESCE(EXCLUDED.finished_at, ci_jobs.finished_at),
          duration_seconds = COALESCE(EXCLUDED.duration_seconds, ci_jobs.duration_seconds)
        RETURNING id;
        """,
        (
            provider,
            repo,
            str(job["pipeline_id"]),
            str(job["job_id"]),
            job.get("name"),
            job.get("status"),
            _normalize_timestamp_to_utc(job.get("started_at")),
            _normalize_timestamp_to_utc(job.get("finished_at")),
            job.get("duration_seconds"),
        ),
    )
    return rows[0][0]


def ingest_ci(
    provider: str,
    repo: str,
    pipelines: Iterable[Dict[str, Any]],
    jobs_by_pipeline: Optional[Dict[str, Iterable[Dict[str, Any]]]] = None,
) -> int:
    count = 0
    for pipe in pipelines:
        upsert_ci_pipeline(provider, repo, pipe)
        pid = str(pipe["pipeline_id"])
        for job in (jobs_by_pipeline or {}).get(pid, []):
            job["pipeline_id"] = pid
            upsert_ci_job(provider, repo, job)
        count += 1
    return count
