from src import db_utils
from src.git_miner import mine_and_store

def test_mine_and_store_inserts_head_commit(temp_git_repo):
    info = mine_and_store(temp_git_repo)
    assert 'hash' in info
    assert info['author_name'] == 'STRATA Student'

    row = db_utils.exec_get_one("SELECT commit_hash, author_name, message FROM commits ORDER BY id DESC LIMIT 1;")
    assert row[0] == info['hash']
    assert row[1] == 'STRATA Student'
    assert 'initial commit' in row[2]
