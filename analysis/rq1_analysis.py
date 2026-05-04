import pandas as pd

def run():
    df = pd.read_csv("output/commit_messages.csv")

    correlation = df["files_changed"].corr(df["message_length"])

    print("\n--- RQ1: Correlation ---")
    print(f"Correlation between files changed and message length: {correlation:.3f}")

    print("\n--- Basic Stats ---")
    print(df[["files_changed", "message_length"]].describe())

if __name__ == "__main__":
    run()