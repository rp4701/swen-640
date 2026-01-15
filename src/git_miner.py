from datetime import datetime
from git import Repo
from . import db_utils

def extract_head_commit(repo_path: str = "."):
    repo = Repo(repo_path)
    try:
        head = repo.head.commit
        return {
            "hash": head.hexsha,
            "author_name": head.author.name or "unknown",
            "message": head.message.strip(),
            "timestamp": datetime.fromtimestamp(head.committed_date),
        }
    finally:
        # Important on Windows to release file handles
        repo.close()

def insert_commit_record(commit_info: dict):
    sql = """
    INSERT INTO commits (commit_hash, author_name, message, commit_ts)
    VALUES (%(hash)s, %(author_name)s, %(message)s, %(timestamp)s);
    """
    db_utils.exec_commit(sql, commit_info)

def mine_and_store(repo_path: str = "."):
    info = extract_head_commit(repo_path)
    insert_commit_record(info)
    return info
