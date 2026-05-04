import pandas as pd
import matplotlib.pyplot as plt

def run():
    df = pd.read_csv("output/commit_messages.csv")

    plt.scatter(df["files_changed"], df["message_length"], alpha=0.3)
    plt.xlabel("Files Changed")
    plt.ylabel("Message Length")
    plt.title("Files Changed vs Message Length")

    plt.savefig("output/rq1_scatter.png")
    plt.show()

if __name__ == "__main__":
    run()