import argparse
import os
import sys
import tempfile
import shutil
from git import Repo

from src import git_miner


def main(argv=None):
    argv = argv or sys.argv[1:]
    p = argparse.ArgumentParser(description="Clone a repository (or use local path) and run git_miner")
    p.add_argument("repo", help="owner/repo (e.g. octocat/Hello-World) or local repo path")
    p.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN) for private repo cloning")
    args = p.parse_args(argv)

    token = args.token or os.environ.get("GITHUB_TOKEN")
    target = args.repo

    tmp_dir = None
    repo_path = target
    try:
        # If given an owner/repo string and it's not a local path, clone it
        if "/" in target and not os.path.isdir(target):
            tmp_dir = tempfile.mkdtemp(prefix="gitminer_")
            if token:
                clone_url = f"https://{token}@github.com/{target}.git"
            else:
                clone_url = f"https://github.com/{target}.git"
            print(f"Cloning {target} into {tmp_dir}...")
            Repo.clone_from(clone_url, tmp_dir)
            repo_path = tmp_dir

        print(f"Running mine_and_store on {repo_path}...")
        info = git_miner.mine_and_store(repo_path)
        print(f"Stored commit {info.get('hash')} by {info.get('author_name')} at {info.get('timestamp')}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
