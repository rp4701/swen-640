import pandas as pd
import matplotlib.pyplot as plt

def plot_commit_types():
    df = pd.read_csv("output/commit_summary.csv")

    counts = df["commit_type"].value_counts()

    counts.plot(kind="bar")
    plt.title("Commit Type Distribution")
    plt.xlabel("Type")
    plt.ylabel("Count")

    plt.savefig("output/commit_type_distribution.png")
    plt.show()


def plot_rq1_scatter():
    df = pd.read_csv("output/commit_messages.csv")

    plt.scatter(df["files_changed"], df["message_length"], alpha=0.3)
    plt.xlabel("Files Changed")
    plt.ylabel("Message Length")
    plt.title("Files Changed vs Message Length")

    plt.savefig("output/rq1_scatter.png")
    plt.show()


def size_category_graph():
    df = pd.read_csv("output/commit_messages.csv")

    df["size_category"] = pd.cut(
        df["files_changed"],
        bins=[-1, 2, 10, 1000],
        labels=["Small", "Medium", "Large"]
    )

    avg_lengths = df.groupby("size_category")["message_length"].mean()

    avg_lengths.plot(kind="bar")
    plt.title("Average Message Length by Commit Size")
    plt.ylabel("Avg Message Length")

    plt.savefig("output/size_vs_length.png")
    plt.show()


if __name__ == "__main__":
    plot_commit_types()
    plot_rq1_scatter()
    size_category_graph()