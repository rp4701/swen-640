import argparse
import os
import sys
import tempfile
import shutil
import csv
from git import Repo

from src import git_miner
from src import qual_clean
from src import sampling_algorithms as sampling
from src import da1_identifiers
from src import srcml_runner


def main(argv=None):
    argv = argv or sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Clone a repository (or use local path) and run analysis pipeline"
    )

    parser.add_argument(
        "repo",
        help="owner/repo (e.g. octocat/Hello-World) or local repo path"
    )

    parser.add_argument(
        "--token",
        help="GitHub token (or set GITHUB_TOKEN env variable)"
    )

    args = parser.parse_args(argv)

    token = args.token or os.environ.get("GITHUB_TOKEN")
    target = args.repo

    tmp_dir = None
    repo_path = target

    try:
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

        print(
            f"Stored commit {info.get('hash')} "
            f"by {info.get('author_name')} "
            f"at {info.get('timestamp')}"
        )

        print("\nDI2 Sampling Demo")

        repo = Repo(repo_path)
        commits = list(repo.iter_commits())

        if not commits:
            print("No commits found for sampling.")
            return

        uniform_sample = sampling.sample_uniform(
            commits, k=min(10, len(commits)), seed=42
        )
        print(f"Uniform sample size: {len(uniform_sample)}")

        systematic_sample = sampling.sample_systematic(
            commits, step=5, seed=42
        )
        print(f"Systematic sample size: {len(systematic_sample)}")

        def author_key(commit):
            return getattr(commit.author, "email", "unknown")

        stratified_sample = sampling.sample_stratified(
            commits,
            key=author_key,
            frac=0.2,
            seed=42,
        )
        print(f"Stratified sample size: {len(stratified_sample)}")

        required_n = sampling.sample_size_proportion(
            N=len(commits),
            p=0.5,
            margin=0.05,
        )
        print(f"Required labeling sample size (95% CI): {required_n}")

        print("\nDA1 Identifier Analysis Demo")

        xml = srcml_runner.run_srcml_on_repo_file(
            repo_path,
            #"src/da1_identifiers.py",
            "src/example.java",
            commit="HEAD",
        )
        

        identifiers = da1_identifiers.extract_identifiers_dom(xml)
        summary = da1_identifiers.aggregate_identifier_features(identifiers)

        print(f"Identifiers extracted: {len(identifiers)}")
        print(summary)

        os.makedirs("output", exist_ok=True)
        output_path = "output/identifier_dataset.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["file_path", *summary.keys()],
            )
            writer.writeheader()
            writer.writerow({
                "file_path": "src/da1_identifiers.py",
                **summary,
            })

        print(f"Dataset written to {output_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()