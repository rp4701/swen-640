import subprocess
import pandas as pd

def extract_from_repo(repo_path):
    result = subprocess.run(
        ["git", "-C", repo_path, "log", "--pretty=format:%H|%s", "--numstat"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    lines = result.stdout.split("\n")

    data = []
    current_commit = None
    files_changed = 0

    for line in lines:
        if "|" in line:  
            if current_commit:
                current_commit["files_changed"] = files_changed
                data.append(current_commit)

            commit_hash, message = line.split("|", 1)
            current_commit = {
                "commit": commit_hash,
                "message": message,
                "files_changed": 0
            }
            files_changed = 0

        elif line.strip() != "":
            parts = line.split("\t")
            if len(parts) == 3:
                files_changed += 1

    
    if current_commit:
        current_commit["files_changed"] = files_changed
        data.append(current_commit)

    return data


def run():
    repos = [
        ".",
        "repos/react"
    ]

    all_data = []

    for repo in repos:
        print(f"Extracting from {repo}...")
        repo_data = extract_from_repo(repo)
        print(f"  → {len(repo_data)} commits found")
        all_data.extend(repo_data)

    df = pd.DataFrame(all_data)

    
    df["message_length"] = df["message"].apply(lambda x: len(str(x).split()))

    df.to_csv("output/commit_messages.csv", index=False)

    print(f"\n Total commits collected: {len(df)}")


if __name__ == "__main__":
    run()