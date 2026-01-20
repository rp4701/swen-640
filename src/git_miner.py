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
