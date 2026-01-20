import os
from git import Repo
import pytest

from src.git_miner import mine_and_store, mine_history, validate_invariants
from src import db_utils


@pytest.fixture(autouse=True)
def reset_db():
    db_utils.exec_sql_file("data/schema.sql")


def seed_two_commit_repo(tmp_path):
    repo = Repo.init(tmp_path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", "STRATA Student")
        cw.set_value("user", "email", "student@example.com")

    file_path = os.path.join(tmp_path, "hello.txt")

    # Commit 1
    with open(file_path, "w") as f:
        f.write("hello\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Initial commit")

    # Commit 2
    with open(file_path, "a") as f:
        f.write("world\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Second commit")

    return tmp_path


# ========== A. Head-mining compatibility ==========

def test_head_mining_dc0_compatibility(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    info = mine_and_store(str(repo_path))

    assert "hash" in info
    assert info["author_name"] == "STRATA Student"

    row = db_utils.exec_get_one(
        "SELECT commit_hash, author_name FROM commits ORDER BY id DESC LIMIT 1;"
    )

    assert row[0] == info["hash"]
    assert row[1] == "STRATA Student"


# ========== B. Full-history mining ==========

def test_full_history_populates_stats_and_files(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    mine_history(str(repo_path))

    n_commits = db_utils.exec_get_one("SELECT COUNT(*) FROM commits;")[0]
    n_stats = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_stats;")[0]

    assert n_commits >= 2
    assert n_stats == n_commits

    row = db_utils.exec_get_one(
        """
        SELECT additions, deletions
        FROM commit_files
        WHERE file_path = 'hello.txt'
        LIMIT 1;
        """
    )

    assert row is not None
    assert row[0] >= 0
    assert row[1] >= 0


# ========== C. Idempotent ETL ==========

def test_idempotent_rerun(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    mine_history(str(repo_path))
    counts1 = (
        db_utils.exec_get_one("SELECT COUNT(*) FROM commits;")[0],
        db_utils.exec_get_one("SELECT COUNT(*) FROM commit_stats;")[0],
        db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0],
    )

    mine_history(str(repo_path))
    counts2 = (
        db_utils.exec_get_one("SELECT COUNT(*) FROM commits;")[0],
        db_utils.exec_get_one("SELECT COUNT(*) FROM commit_stats;")[0],
        db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0],
    )

    assert counts1 == counts2


# ========== D. Provenance in run_log ==========

def test_run_log_records_provenance(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    count = mine_history(str(repo_path), record_run=True)

    row = db_utils.exec_get_one(
        """
        SELECT repo_path, head_hash, commit_count
        FROM run_log
        ORDER BY id DESC
        LIMIT 1;
        """
    )

    assert row is not None
    assert str(repo_path) in row[0]
    assert row[2] == count

    head = db_utils.exec_get_one(
        "SELECT commit_hash FROM commits ORDER BY id DESC LIMIT 1;"
    )[0]

    assert row[1] == head


# ========== E. Validation invariants ==========

def test_validation_invariants(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    mine_history(str(repo_path))

    n_commits, n_stats, n_orphans = validate_invariants()

    assert n_commits >= 2
    assert n_stats == n_commits
    assert n_orphans == 0


# ========== F. Additional Tests ==========

# 1) Root commit has no parents
def test_root_commit_has_no_parent(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    mine_history(str(repo_path))

    parents = db_utils.exec_get_one(
        "SELECT COUNT(*) FROM commit_parents WHERE commit_id = 1;"
    )[0]

    assert parents == 0


# 2) New file creates a new commit_files row
def test_new_file_creates_file_row(tmp_path):
    repo = Repo.init(tmp_path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", "STRATA Student")
        cw.set_value("user", "email", "student@example.com")

    file1 = os.path.join(tmp_path, "hello.txt")
    with open(file1, "w") as f:
        f.write("hello\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Initial commit")

    file2 = os.path.join(tmp_path, "readme.md")
    with open(file2, "w") as f:
        f.write("Readme\n")
    repo.index.add(["readme.md"])
    repo.index.commit("Add readme")

    mine_history(str(tmp_path))

    files = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0]
    assert files >= 2
