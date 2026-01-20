import os
from git import Repo
import pytest

from src.git_miner import mine_history
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


def test_unique_constraints_prevent_duplicates(tmp_path):
    repo_path = seed_two_commit_repo(tmp_path)

    # First run
    mine_history(str(repo_path))

    counts_1 = {
        "commits": db_utils.exec_get_one("SELECT COUNT(*) FROM commits;")[0],
        "files": db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0],
    }

    # Second run (should not duplicate anything)
    mine_history(str(repo_path))

    counts_2 = {
        "commits": db_utils.exec_get_one("SELECT COUNT(*) FROM commits;")[0],
        "files": db_utils.exec_get_one("SELECT COUNT(*) FROM commit_files;")[0],
    }

    assert counts_1 == counts_2
