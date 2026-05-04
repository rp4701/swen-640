import subprocess
import pandas as pd

def get_files_for_commit(repo, commit_hash):
    result = subprocess.run(
        ["git", "-C", repo, "show", "--name-only", "--pretty=", commit_hash],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    files = result.stdout.split("\n")
    return [f for f in files if f.strip() != ""]


def check_match(message, files):
    message = message.lower()
    for f in files:
        name = f.split("/")[-1].lower()
        name = name.replace(".js", "").replace(".py", "")
        if name in message:
            return 1
    return 0


def run():
    df = pd.read_csv("output/commit_messages.csv")

    matches = []

    for i, row in df.head(500).iterrows():
        repo = "." if i < 100 else "repos/react"
        files = get_files_for_commit(repo, row["commit"])
        match = check_match(row["message"], files)
        matches.append(match)

    df = df.head(len(matches))
    df["matches"] = matches

    match_rate = df["matches"].mean()

    print("\n--- RQ2: Message-File Alignment ---")
    print(f"Match rate: {match_rate:.2f}")

if __name__ == "__main__":
    run()