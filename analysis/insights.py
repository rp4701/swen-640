import pandas as pd

def run():
    df = pd.read_csv("output/commit_summary.csv")

    print("\n--- Commit Type Distribution ---")
    print(df["commit_type"].value_counts())

    print("\n--- Average Message Length ---")
    df["msg_length"] = df.iloc[:, 0].astype(str).apply(len)
    print(df["msg_length"].mean())

if __name__ == "__main__":
    run()