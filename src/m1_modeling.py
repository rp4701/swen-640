from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt
import re
from collections import Counter
from src.da2_vocabulary import extract_vocabulary  # <-- IMPORTANT (connects M1 to DA2)

# ---------------------------------------------------------------------------
# Commit type classification constants
# ---------------------------------------------------------------------------

COMMIT_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "fix":      ["fix", "bug", "patch", "hotfix", "error", "repair",
                 "correct", "typo", "broke", "broken", "revert", "crash", "fail"],
    "feature":  ["feat", "add", "new", "implement", "introduce", "create",
                 "support", "feature", "initial", "allow", "enable"],
    "refactor": ["refactor", "cleanup", "clean", "reorganize", "rename",
                 "restructure", "move", "extract", "simplify", "rewrite", "split"],
    "test":     ["test", "tests", "spec", "specs", "assert", "coverage",
                 "mock", "pytest", "unittest"],
    "docs":     ["doc", "docs", "readme", "changelog", "documentation",
                 "guide", "docstring"],
}

_TYPE_PRIORITY = ["fix", "feature", "refactor", "test", "docs"]


def label_commit(message: str) -> str:
    if not message or not message.strip():
        return "other"

    text = message.lower()

    for label in _TYPE_PRIORITY:
        for kw in COMMIT_TYPE_KEYWORDS[label]:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return label

    return "other"


def build_commit_features(
    tokens: List[str],
    token_to_cluster: Dict[str, int],
    k: int,
    identifier_tokens: Optional[List[str]] = None,
    comment_tokens: Optional[List[str]] = None,
) -> np.ndarray:

    features = np.zeros(k + 4, dtype=float)

    if not tokens:
        return features

    total_tokens = len(tokens)

    cluster_counts = Counter()
    for t in tokens:
        if t in token_to_cluster:
            cluster_counts[token_to_cluster[t]] += 1

    for cluster_id, count in cluster_counts.items():
        if 0 <= cluster_id < k:
            features[cluster_id] = count / total_tokens

    features[k] = np.log1p(total_tokens)

    unique_tokens = len(set(tokens))
    features[k + 1] = unique_tokens / total_tokens if total_tokens > 0 else 0.0

    token_set = set(tokens)

    id_set = set(identifier_tokens) if identifier_tokens else set()
    union = token_set | id_set
    inter = token_set & id_set
    features[k + 2] = len(inter) / len(union) if union else 0.0

    comment_set = set(comment_tokens) if comment_tokens else set()
    union = token_set | comment_set
    inter = token_set & comment_set
    features[k + 3] = len(inter) / len(union) if union else 0.0

    return features


def build_feature_matrix(
    commit_records: List[Dict[str, str]],
    k: int = 5,
    token_to_cluster: Optional[Dict[str, int]] = None,
    identifier_tokens: Optional[List[str]] = None,
    comment_tokens: Optional[List[str]] = None,
) -> Tuple[np.ndarray, List[str], List[str]]:

    feature_names = (
        [f"cluster_{i}_frac" for i in range(k)] +
        ["log_token_count", "type_token_ratio", "id_overlap", "comment_overlap"]
    )

    if not commit_records:
        return np.zeros((0, k + 4)), [], feature_names

    if token_to_cluster is None:
        token_to_cluster = {}

    X = []
    y = []

    for record in commit_records:
        msg = record.get("message", "")

        # Use DA2 tokenizer instead of regex
        tokens = extract_vocabulary([msg])

        features = build_commit_features(
            tokens,
            token_to_cluster,
            k,
            identifier_tokens,
            comment_tokens,
        )

        X.append(features)
        y.append(label_commit(msg))

    X = np.array(X)

    return X, y, feature_names


def split_dataset(
    X: np.ndarray,
    y: List[str],
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:

    from sklearn.model_selection import train_test_split

    label_counts = Counter(y)

    stratify = y if all(c >= 2 for c in label_counts.values()) else None

    if stratify is None:
        print("Warning: some classes have <2 samples; falling back to non-stratified split.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )

    return X_train, X_test, y_train, y_test


def train_classifier(
    X_train: np.ndarray,
    y_train: List[str],
    model_type: str = "decision_tree",
    max_depth: Optional[int] = None,
) -> Any:

    if model_type == "decision_tree":
        from sklearn.tree import DecisionTreeClassifier
        model = DecisionTreeClassifier(max_depth=max_depth, random_state=42)

    elif model_type == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=max_depth,
            random_state=42,
        )

    else:
        raise ValueError("model_type must be 'decision_tree' or 'random_forest'")

    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: List[str],
) -> Dict[str, Any]:

    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

    y_pred = model.predict(X_test)

    class_names = sorted(set(y_test))

    acc = accuracy_score(y_test, y_pred)

    report = classification_report(
        y_test,
        y_pred,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(
        y_test,
        y_pred,
        labels=class_names,
    )

    return {
        "accuracy": acc,
        "classification_report": report,
        "confusion_matrix": cm,
        "class_names": class_names,
        "y_pred": y_pred,
    }


def plot_feature_importance(
    model: Any,
    feature_names: List[str],
    output_path: Optional[str] = None,
) -> None:
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]

    plt.figure(figsize=(10, 6))
    plt.bar(
        range(len(importances)),
        importances[indices],
        color='steelblue',
        edgecolor='black',
        linewidth=0.5,
    )
    plt.xticks(
        range(len(importances)),
        [feature_names[i] for i in indices],
        rotation=45,
        ha='right',
        fontsize=9,
    )
    plt.xlabel("Feature", fontsize=12)
    plt.ylabel("Importance", fontsize=12)
    plt.title("Feature Importances", fontsize=14, fontweight='bold')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    else:
        plt.show()


def plot_confusion_matrix(
    y_true: List[str],
    y_pred: Any,
    class_names: List[str],
    output_path: Optional[str] = None,
) -> None:
    from sklearn.metrics import confusion_matrix as sk_cm

    cm = sk_cm(y_true, y_pred, labels=class_names)

    plt.figure(figsize=(8, 6))
    im = plt.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.colorbar(im, label='Count')
    plt.title('Confusion Matrix', fontsize=14, fontweight='bold')
    plt.xlabel('Predicted Label', fontsize=12)
    plt.ylabel('True Label', fontsize=12)

    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=45, ha='right', fontsize=9)
    plt.yticks(tick_marks, class_names, fontsize=9)

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(
                j, i, str(cm[i, j]),
                ha='center', va='center',
                color='white' if cm[i, j] > thresh else 'black',
                fontsize=10,
            )

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    else:
        plt.show()


def load_commit_data(commit_limit: Optional[int] = None) -> List[Dict[str, str]]:
    from src import db_utils

    query = "SELECT TRIM(message) FROM commits WHERE message IS NOT NULL"
    if commit_limit:
        query += f" LIMIT {int(commit_limit)}"
    query += ";"

    try:
        rows = db_utils.exec_get_all(query)
    except Exception as exc:
        print(f"[load_commit_data] DB query failed: {exc}")
        return []

    return [
        {"message": str(row[0])}
        for row in rows
        if row[0] and str(row[0]).strip()
    ]