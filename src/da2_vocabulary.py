from typing import Any, Dict, List, Tuple, Optional
import re
import numpy as np
import xml.etree.ElementTree as ET
from src import db_utils

# --- matplotlib (headless mode for tests) ---
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- ML / NLP ---
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import adjusted_rand_score

import spacy
from nltk.stem import PorterStemmer


# ============================================================
# Comment Extraction
# ============================================================

def extract_comments_from_srcml(xml_str: str) -> List[str]:
    comments: List[str] = []

    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return comments

    for elem in root.iter():
        if elem.tag.endswith("comment"):
            text = elem.text or ""

            text = re.sub(r"^\s*/\*", "", text)
            text = re.sub(r"\*/\s*$", "", text)
            text = re.sub(r"^\s*//", "", text, flags=re.MULTILINE)
            text = re.sub(r"^\s*#", "", text, flags=re.MULTILINE)
            text = re.sub(r"^\s*\*\s?", "", text, flags=re.MULTILINE)

            text = text.strip()

            if text:
                comments.append(text)

    return comments


# ============================================================
# Vocabulary Extraction
# ============================================================

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "this", "that",
    "and", "or", "to", "of", "in", "on", "for", "with", "as",
    "by", "at", "from", "it", "be", "has", "have", "had"
}

_STEMMER = PorterStemmer()


def extract_vocabulary(
    text_list: List[str],
    min_length: int = 3,
    remove_stopwords: bool = True,
    stem: bool = True
) -> List[str]:

    tokens: List[str] = []

    for text in text_list:
        if text is None:
            continue

        words = re.findall(r"\b\w+\b", str(text).lower())

        for w in words:
            if w.isnumeric():
                continue

            if len(w) < min_length:
                continue

            if remove_stopwords and w in _STOPWORDS:
                continue

            if stem:
                w = _STEMMER.stem(w)

            tokens.append(w)

    return tokens


# ============================================================
# spaCy loader (safe for student environments)
# ============================================================

_nlp = None


def _get_spacy():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_md")
        except OSError:
            # fallback if model not installed
            _nlp = spacy.blank("en")
    return _nlp


# ============================================================
# Clustering
# ============================================================

def cluster_vocabulary(
    tokens: List[str],
    k: int = 5,
    vectorizer_params: Optional[Dict[str, Any]] = None
) -> Tuple[np.ndarray, np.ndarray, Any]:

    # ---- empty input ----
    if len(tokens) == 0:
        return np.array([]), np.empty((0, 0)), None

    nlp = _get_spacy()

    vectors_list = []

    for token in tokens:
        vec = nlp(token).vector

        # fallback if spaCy model has no embeddings
        if vec.size == 0:
            # deterministic 300-dim vector (matches en_core_web_md size)
            rng = np.random.default_rng(abs(hash(token)) % (2**32))
            vec = rng.random(300)

        vectors_list.append(vec)

    vectors = np.vstack(vectors_list)

    # adjust k safely
    k = min(k, len(tokens))

    if k <= 1:
        labels = np.zeros(len(tokens), dtype=int)
        return labels, vectors, None

    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(vectors)

    return labels, vectors, model


# ============================================================
# Dimensionality Reduction
# ============================================================

def reduce_dimensions(
    vectors: np.ndarray,
    n_components: int = 2,
    method: str = "pca"
) -> np.ndarray:

    if vectors.shape[0] == 0:
        return np.empty((0, n_components))

    method = method.lower()

    if method == "pca":
        reducer = PCA(n_components=n_components)
        return reducer.fit_transform(vectors)

    elif method == "tsne":
        reducer = TSNE(
            n_components=n_components,
            random_state=42,
            init="random",
            learning_rate="auto"
        )
        return reducer.fit_transform(vectors)

    else:
        raise ValueError("method must be 'pca' or 'tsne'")


# ============================================================
# Visualization (Provided)
# ============================================================

def visualize_clusters(
    coords_2d: np.ndarray,
    labels: np.ndarray,
    tokens: List[str],
    title: str = "Vocabulary Clusters",
    output_path: Optional[str] = None
) -> None:

    if coords_2d.shape[0] == 0:
        plt.figure(figsize=(10, 8))
        plt.title(title)
        plt.xlabel("Dimension 1")
        plt.ylabel("Dimension 2")
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
        return

    plt.figure(figsize=(10, 8))
    scatter = plt.scatter(
        coords_2d[:, 0],
        coords_2d[:, 1],
        c=labels,
        cmap='tab10',
        alpha=0.6,
        s=50,
        edgecolors='black',
        linewidth=0.5
    )

    n_clusters = len(np.unique(labels))
    if n_clusters <= 10:
        plt.colorbar(scatter, label='Cluster ID', ticks=range(n_clusters))
    else:
        plt.colorbar(scatter, label='Cluster ID')

    for cluster_id in np.unique(labels):
        cluster_mask = labels == cluster_id
        cluster_indices = np.where(cluster_mask)[0]
        if len(cluster_indices) > 0:
            cluster_coords = coords_2d[cluster_mask]
            centroid = cluster_coords.mean(axis=0)
            distances = np.linalg.norm(cluster_coords - centroid, axis=1)
            rep_idx = cluster_indices[np.argmin(distances)]
            if rep_idx < len(tokens):
                plt.annotate(
                    tokens[rep_idx],
                    xy=(coords_2d[rep_idx, 0], coords_2d[rep_idx, 1]),
                    xytext=(5, 5),
                    textcoords='offset points',
                    fontsize=8,
                    alpha=0.7
                )

    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel("Dimension 1")
    plt.ylabel("Dimension 2")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    else:
        plt.show()


# ============================================================
# Alignment Metrics
# ============================================================

def measure_alignment(
    tokens_a: List[str],
    tokens_b: List[str],
    labels_a: np.ndarray,
    labels_b: np.ndarray
) -> Dict[str, float]:

    set_a = set(tokens_a)
    set_b = set(tokens_b)

    intersection = set_a & set_b
    union = set_a | set_b

    vocab_overlap = len(intersection) / len(union) if union else 0.0
    shared_vocab_size = len(intersection)

    if shared_vocab_size == 0:
        cluster_similarity = 0.0
    else:
        map_a = {}
        map_b = {}

        for t, l in zip(tokens_a, labels_a):
            if t in intersection and t not in map_a:
                map_a[t] = l

        for t, l in zip(tokens_b, labels_b):
            if t in intersection and t not in map_b:
                map_b[t] = l

        shared_tokens = [
            t for t in intersection if t in map_a and t in map_b
        ]

        labels_shared_a = [map_a[t] for t in shared_tokens]
        labels_shared_b = [map_b[t] for t in shared_tokens]

        if len(labels_shared_a) < 2:
            cluster_similarity = 0.0
        else:
            cluster_similarity = adjusted_rand_score(
                labels_shared_a,
                labels_shared_b
            )

    return {
        "vocab_overlap": float(vocab_overlap),
        "shared_vocab_size": int(shared_vocab_size),
        "cluster_similarity": float(cluster_similarity),
    }


# ============================================================
# Dataset Builder (stub integration)
# ============================================================

def build_vocabulary_dataset(
    repo_path: str = ".",
    commit_limit: Optional[int] = None,
    file_limit: Optional[int] = None
) -> Dict[str, Any]:

    # -------------------------------
    # LOAD IDENTIFIERS FROM DB
    # -------------------------------
    identifier_rows = db_utils.exec_get_all(
        "SELECT name FROM code_identifiers;"
    )

    identifier_texts = [r[0] for r in identifier_rows if r and r[0]]

    identifier_tokens = extract_vocabulary(
        identifier_texts,
        remove_stopwords=False,
        stem=False
    )

    # -------------------------------
    # LOAD COMMENTS FROM DB
    # -------------------------------
    comment_rows = db_utils.exec_get_all(
        "SELECT comment_text FROM code_comments;"
    )

    comment_texts = [r[0] for r in comment_rows if r and r[0]]

    comment_tokens = extract_vocabulary(
        comment_texts,
        remove_stopwords=True,
        stem=True
    )

    # -------------------------------
    # COMMITS (optional for now)
    # -------------------------------
    commit_tokens: List[str] = []

    # -------------------------------
    # CLUSTERING
    # -------------------------------
    commit_labels, _, _ = cluster_vocabulary(commit_tokens, k=5)
    identifier_labels, _, _ = cluster_vocabulary(identifier_tokens, k=5)
    comment_labels, _, _ = cluster_vocabulary(comment_tokens, k=5)

    # -------------------------------
    # ALIGNMENT METRICS
    # -------------------------------
    alignment = {
        "commit_identifier": measure_alignment(
            commit_tokens,
            identifier_tokens,
            commit_labels,
            identifier_labels,
        ),
        "commit_comment": measure_alignment(
            commit_tokens,
            comment_tokens,
            commit_labels,
            comment_labels,
        ),
        "identifier_comment": measure_alignment(
            identifier_tokens,
            comment_tokens,
            identifier_labels,
            comment_labels,
        ),
    }

    return {
        "commit_tokens": commit_tokens,
        "identifier_tokens": identifier_tokens,
        "comment_tokens": comment_tokens,
        "commit_labels": commit_labels,
        "identifier_labels": identifier_labels,
        "comment_labels": comment_labels,
        "alignment": alignment,
    }