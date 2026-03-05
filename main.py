import argparse
import os
import sys
import tempfile
import shutil
import csv
import xml.etree.ElementTree as ET
import threading
from git import Repo
from collections import Counter

from src import git_miner
from src import qual_clean
from src import sampling_algorithms as sampling
from src import da1_identifiers
from src import srcml_runner
from src import db_utils
from src import da2_vocabulary
from src.da2_vocabulary import build_vocabulary_dataset
from src import m1_modeling


# DA2: Mine Code Artifacts (Identifiers + Comments)

def _mine_code_artifacts(repo_path: str, file_limit: int = None) -> None:
    print("  Running srcML on repository directory...")

    #db_utils.exec_sql_file("data/schema.sql")

    try:
        db_utils.exec_commit("DELETE FROM code_identifiers;")
        db_utils.exec_commit("DELETE FROM code_comments;")
    except Exception:
        pass

    print("  Scanning source files...")

    supported_ext = (".py", ".java", ".c", ".cpp", ".h", ".hpp", ".js")
    units = []

    try:
        srcml_path = srcml_runner.find_srcml_executable()
    except Exception as exc:
        print(f"  Warning: srcML not found ({exc})", file=sys.stderr)
        return

    import subprocess

    for root_dir, _, files in os.walk(repo_path):
        if ".git" in root_dir:
            continue

        for fname in files:
            if not fname.lower().endswith(supported_ext):
                continue

            file_path = os.path.join(root_dir, fname)

            try:
                result = subprocess.run(
                    [srcml_path, file_path],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                element = ET.fromstring(result.stdout.encode("utf-8"))
                element.set("filename", os.path.relpath(file_path, repo_path))

                units.append(element)

            except Exception:
                continue

            if file_limit and len(units) >= file_limit:
                break
        if file_limit and len(units) >= file_limit:
            break

    print(f"  Processing {len(units)} source files...")

    id_rows = []
    cm_rows = []
    all_identifiers_summary = {}

    for unit in units:
        rel_path = unit.get("filename", "")
        unit_xml = ET.tostring(unit, encoding="unicode")

        # ---- DA1 identifiers ----
        try:
            identifiers = da1_identifiers.extract_identifiers_dom(unit_xml)
            for row in identifiers:
                id_rows.append({"fp": rel_path, "name": row["name"], "kind": row["kind"]})
            summary = da1_identifiers.aggregate_identifier_features(identifiers)
            all_identifiers_summary.update(summary)
        except Exception:
            identifiers = []

        # ---- DA2 comments ----
        try:
            for text in da2_vocabulary.extract_comments_from_srcml(unit_xml):
                if text.strip():
                    cm_rows.append({"fp": rel_path, "ct": text})
        except Exception:
            pass

    db_utils.exec_many(
        "INSERT INTO code_identifiers (file_path, name, kind) VALUES (%(fp)s, %(name)s, %(kind)s);",
        id_rows,
    )

    db_utils.exec_many(
        "INSERT INTO code_comments (file_path, comment_text) VALUES (%(fp)s, %(ct)s);",
        cm_rows,
    )

    print(f"    -> {len(id_rows)} identifiers, {len(cm_rows)} comments stored")

    os.makedirs("output", exist_ok=True)
    output_path = "output/identifier_dataset.csv"

    if all_identifiers_summary:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_path", *all_identifiers_summary.keys()])
            writer.writeheader()
            writer.writerow({"file_path": "repository", **all_identifiers_summary})
        print(f"Identifier summary CSV written to {output_path}")


# DA2 Analyze Stage

def cmd_analyze(args) -> None:
    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    k = args.clusters

    print("Building vocabulary dataset from DB...")

    dataset = da2_vocabulary.build_vocabulary_dataset(
        commit_limit=args.commit_limit,
        file_limit=args.file_limit,
    )

    commit_tokens = dataset["commit_tokens"]
    identifier_tokens = dataset["identifier_tokens"]
    comment_tokens = dataset["comment_tokens"]

    print(f"  commit tokens: {len(commit_tokens)}")
    print(f"  identifier tokens: {len(identifier_tokens)}")
    print(f"  comment tokens: {len(comment_tokens)}")

    if not commit_tokens:
        print("Warning: No commit tokens found. Ensure git_miner completed successfully.")

    sources = [
        ("commit", commit_tokens, "Commit Message Vocabulary"),
        ("identifier", identifier_tokens, "Code Identifier Vocabulary"),
        ("comment", comment_tokens, "Code Comment Vocabulary"),
    ]

    for name, tokens, title in sources:
        if not tokens:
            print(f"[{name}] no tokens — skipping")
            continue
        print(f"Clustering {name} tokens (k={k})...")
        labels, vectors, _ = da2_vocabulary.cluster_vocabulary(tokens, k=k)
        coords = da2_vocabulary.reduce_dimensions(vectors, method="pca")
        da2_vocabulary.visualize_clusters(coords, labels, tokens, title=f"{title} – k-means (k={k})",
                                          output_path=os.path.join(out, f"{name}_clusters.png"))

    alignment = dataset.get("alignment", {})

    if commit_tokens:
        report_lines = ["VOCABULARY ALIGNMENT REPORT", "=" * 40, ""]
        for key, m in alignment.items():
            report_lines += [
                key,
                f"  Vocabulary overlap: {m['vocab_overlap']:.1%}",
                f"  Shared vocabulary size: {m['shared_vocab_size']}",
                f"  Cluster similarity (ARI): {m['cluster_similarity']:.3f}",
                "",
            ]
        report_path = os.path.join(out, "alignment_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"Report written → {report_path}")
    else:
        print("Skipping alignment report due to no commit tokens.")


# ---------------- M1 Predict ----------------

def cmd_predict(args) -> None:
    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    print("Loading commit data from DB...")
    commit_records = m1_modeling.load_commit_data(
        commit_limit=args.commit_limit
    )

    print(f"  {len(commit_records)} commits loaded")

    if not commit_records:
        print("No commits found.")
        return

    try:
        id_rows = db_utils.exec_get_all("SELECT name FROM code_identifiers;")
        identifier_tokens = da2_vocabulary.extract_vocabulary(
            [r[0] for r in id_rows if r[0]]
        )

        cm_rows = db_utils.exec_get_all("SELECT comment_text FROM code_comments;")
        comment_tokens = da2_vocabulary.extract_vocabulary(
            [r[0] for r in cm_rows if r[0]]
        )

    except Exception as e:
        print(f"Warning loading identifier/comment tokens: {e}")
        identifier_tokens = []
        comment_tokens = []

    print("Building feature matrix...")

    X, y, feature_names = m1_modeling.build_feature_matrix(
        commit_records,
        k=args.clusters,
        identifier_tokens=identifier_tokens,
        comment_tokens=comment_tokens,
    )

    print(f"X shape: {X.shape}")
    print(f"Label distribution: {dict(Counter(y))}")

    if len(set(y)) < 2:
        print("Only one class label found. Cannot train model.")
        return

    X_train, X_test, y_train, y_test = m1_modeling.split_dataset(X, y)

    print("Training classifier...")

    model = m1_modeling.train_classifier(
        X_train,
        y_train,
        model_type=args.model_type,
        max_depth=args.max_depth,
    )

    results = m1_modeling.evaluate_model(model, X_test, y_test)

    print(f"Accuracy: {results['accuracy']:.1%}")

    fi_path = os.path.join(out, "feature_importance.png")
    cm_path = os.path.join(out, "confusion_matrix.png")

    m1_modeling.plot_feature_importance(
        model,
        feature_names,
        output_path=fi_path,
    )

    m1_modeling.plot_confusion_matrix(
        y_test,
        results["y_pred"],
        results["class_names"],
        output_path=cm_path,
    )

    print(f"Saved plots → {fi_path}, {cm_path}")
    # Build classification report text
    from sklearn.metrics import classification_report

    clf_report_text = classification_report(
        y_test,
        results["y_pred"],
        labels=results["class_names"],
        zero_division=0,
    )

    # Write model report
    report_lines = [
        "M1 MODEL REPORT",
        "=" * 40,
        "",
        f"Model type:  {args.model_type}",
        f"Features:    {len(feature_names)}",
        f"Train size:  {len(X_train)}",
        f"Test size:   {len(X_test)}",
        f"Accuracy:    {results['accuracy']:.1%}",
        "",
        "Classification report (test set):",
        "-" * 36,
        clf_report_text,
        "Feature importances (descending):",
        "-" * 36,
    ]

    importances = model.feature_importances_
    ranked = sorted(zip(feature_names, importances), key=lambda x: -x[1])

    for name, imp in ranked:
        report_lines.append(f"  {name:<25} {imp:.4f}")

    report_lines += [
        "",
        "Interpretation:",
        "  [TODO: Write 2-3 sentences interpreting your results here]",
    ]

    report_path = os.path.join(out, "model_report.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"Saved report → {report_path}")
def main(argv=None):
    argv = argv or sys.argv[1:]

    parser = argparse.ArgumentParser(description="Clone a repository (or use local path) and run analysis pipeline")
    parser.add_argument("repo")
    parser.add_argument("--token")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("-k", "--clusters", type=int, default=5)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--commit-limit", type=int, default=None)
    parser.add_argument("--file-limit", type=int, default=None)
    parser.add_argument("--model-type", default="decision_tree", choices=["decision_tree", "random_forest"])
    parser.add_argument("--max-depth", type=int, default=None)

    args = parser.parse_args(argv)
    run_analysis_after = args.analyze

    token = args.token or os.environ.get("GITHUB_TOKEN")
    target = args.repo
    tmp_dir = None
    repo_path = target

    try:
        if "/" in target and not os.path.isdir(target):
            tmp_dir = tempfile.mkdtemp(prefix="gitminer_")
            clone_url = f"https://{token}@github.com/{target}.git" if token else f"https://github.com/{target}.git"
            print(f"Cloning {target} into {tmp_dir}...")
            Repo.clone_from(clone_url, tmp_dir)
            repo_path = tmp_dir

        print(f"Running mine_and_store on {repo_path}...")

        try:
            db_utils.exec_commit("TRUNCATE commit_files CASCADE;")
            db_utils.exec_commit("TRUNCATE commit_stats CASCADE;")
            db_utils.exec_commit("TRUNCATE commit_parents CASCADE;")
            db_utils.exec_commit("TRUNCATE commits CASCADE;")
        except Exception:
            pass

        result_holder = {"info": None, "error": None}
        def run_miner():
            try:
                result_holder["info"] = git_miner.mine_and_store(repo_path)
            except Exception as e:
                result_holder["error"] = e
        t = threading.Thread(target=run_miner, daemon=True)
        t.start()
        t.join(timeout=300)

        if result_holder["error"]:
            raise result_holder["error"]

        if result_holder["info"]:
            info = result_holder["info"]
            print(f"Stored commit {info.get('hash')} by {info.get('author_name')} at {info.get('timestamp')}")

        _mine_code_artifacts(repo_path)

        print("\nDI2 Sampling Demo")
        repo = Repo(repo_path)
        commits = list(repo.iter_commits())

        if commits:
            uniform_sample = sampling.sample_uniform(commits, k=min(10, len(commits)), seed=42)
            print(f"Uniform sample size: {len(uniform_sample)}")

        if run_analysis_after:
            print("\nStarting DA2 analysis...")
            cmd_analyze(args)

        if args.predict:
            print("\nStarting M1 prediction...")
            cmd_predict(args)

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()