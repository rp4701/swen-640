import pandas as pd

def classify_commit(message):
    message = str(message).lower()

    if "fix" in message or "bug" in message:
        return "Bug Fix"
    elif "add" in message or "feature" in message:
        return "Feature"
    elif "refactor" in message:
        return "Refactor"
    elif "doc" in message:
        return "Documentation"
    else:
        return "Other"

def run():
    df = pd.read_csv("output/commit_messages.csv")

    column = "message" if "message" in df.columns else df.columns[0]

    df["commit_type"] = df[column].apply(classify_commit)

    df.to_csv("output/commit_summary.csv", index=False)
    print(" commit_summary.csv created")

if __name__ == "__main__":
    run()