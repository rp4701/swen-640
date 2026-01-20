import os
from git import Repo
import pytest

from src.git_miner import mine_and_store, validate_invariants
from src import db_utils

@pytest.fixture(autouse=True)
def reset_db():
    db_utils.exec_sql_file("data/schema.sql")


def seed_two_commit_repo(tmp_path):
    repo = Repo.init(tmp_path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test User")
        cw.set_value("user", "email", "test@example.com")

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


def test_two_commit_linear_history(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    count = mine_and_store(str(repo_path))
    assert count is not None

    n_commits, n_stats, n_orphans = validate_invariants()

    assert n_commits == 2
    assert n_stats == 2
    assert n_orphans == 0

    parents = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_parents;")[0]
    assert parents == 1

    files = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0]
    assert files >= 2


def test_idempotency_replay(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    mine_and_store(str(repo_path))
    mine_and_store(str(repo_path))  # replay

    n_commits, n_stats, n_orphans = validate_invariants()

    assert n_commits == 2
    assert n_stats == 2
    assert n_orphans == 0

    parents = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_parents;")[0]
    assert parents == 1


def test_new_file_commit(tmp_path):
    repo = Repo.init(tmp_path)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test User")
        cw.set_value("user", "email", "test@example.com")

    # Commit 1
    file1 = os.path.join(tmp_path, "hello.txt")
    with open(file1, "w") as f:
        f.write("hello\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Initial commit")

    # Commit 2
    with open(file1, "a") as f:
        f.write("world\n")
    repo.index.add(["hello.txt"])
    repo.index.commit("Second commit")

    # Commit 3 (new file)
    file2 = os.path.join(tmp_path, "readme.md")
    with open(file2, "w") as f:
        f.write("# Readme\n")
    repo.index.add(["readme.md"])
    repo.index.commit("Add readme")

    mine_and_store(str(tmp_path))

    n_commits, n_stats, n_orphans = validate_invariants()

    assert n_commits == 3
    assert n_stats == 3
    assert n_orphans == 0

    files = db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0]
    assert files >= 3
