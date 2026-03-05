# STRATA — DC2: Ecosystem Artifacts (Data Collection II)

This assignment builds on DC1 by extending the mining pipeline to collect
ecosystem-level artifacts such as issues, pull/merge requests, and CI
pipelines/jobs, while keeping all DC1 behavior intact.

The focus is on provider-agnostic ingestion, idempotent ETL, and
reproducible, test-driven data collection.

---

## DC1 Continuity

All DC1 functionality remains unchanged and continues to pass:

- Full commit history mining (oldest → newest)
- Commit metadata storage
- Parent relationships
- Aggregate commit stats
- Per-file change stats
- Provenance tracking via `run_log`
- Idempotent re-runs
- Programmatic invariant validation

---

## New Functions (DC2)

The miner was extended with provider-agnostic ingestion helpers:

- `ingest_issues` / `upsert_issue`
- `ingest_pull_requests` / `upsert_pull_request`
- `ingest_ci`
- `upsert_ci_pipeline`
- `upsert_ci_job`
- `_normalize_timestamp_to_utc` for consistent TIMESTAMPTZ handling

All inserts use composite unique keys and conflict-aware upserts to ensure
safe re-runs.

---

## New Tests (DC2)

The following tests were added:

- Issues and pull requests ingestion with idempotent replays
- Pull request state normalization (`merged` vs `closed`)
- CI pipelines and jobs ingestion with replay safety
- CI pipeline SHA validation against mined commits
- Timestamp coercion for multiple ISO8601 formats
- Validation invariants (no orphan parents, stats aligned with commits)

All tests are deterministic and network-free.

---

## Commands

Initialize schema:
```bash
python -c "from src import db_utils; db_utils.exec_sql_file('data/schema.sql')"

 DI1: Data Integrity I — Qualitative Text Normalization

This iteration builds on DC2 by normalizing qualitative text artifacts
collected from software repositories. The goal is to reduce noise and
inconsistencies in raw data prior to downstream modeling and analysis.

DI1 introduces deterministic, test-driven normalization of user identities,
free-text fields, and commit messages, while preserving all existing DC
behavior.

### Normalized Artifacts

The following transformations are applied:

- **User canonicalization**
  - Contributor logins are lowercased and whitespace-normalized
  - Common bot accounts (e.g., dependabot, renovate, github-actions) are detected
  - Results stored as `author_norm` and `is_bot`

- **Text normalization**
  - Markdown removed from issue and pull request titles
  - Inline and fenced code preserved using `<CODE>` markers
  - Whitespace, newlines, and control characters normalized
  - Results stored as `title_clean`

- **Conventional Commit parsing**
  - Commit messages parsed into subject, body, type, scope, and breaking flag
  - Supports common Conventional Commit formats (e.g., `feat`, `fix`, `!`)
  - Results stored in `subject`, `body`, `cc_type`, `cc_scope`, `cc_breaking`

### Database Integration

Normalized data is written to additional columns on existing tables.
Schema updates are handled automatically via idempotent helpers
and do not require manual modification.

### Running with DI1 Enabled

After mining raw data, qualitative normalization can be applied by running:

```bash
pytest test/test_qual_clean.py -v


## DI2: Data Integrity II — Sampling & Sample Size

DI2 introduces a reproducible sampling library to prepare mined repository
data for statistically valid analysis. The goal is to support deterministic
sampling and estimate how many artifacts must be analyzed to achieve a
desired margin of error.

### Implemented Features

**Implemented in `src/sampling_algorithms.py`:**

- **Uniform sampling** — random sampling without replacement
- **Stratified sampling** — balanced sampling across groups using `n` or `frac`
- **Systematic sampling** — random start followed by every *k*-th item
- **Sample size (proportion)** — computes required sample size with finite population correction
- **Sample size (mean)** — computes required sample size for estimating averages

All sampling is deterministic when a seed is provided using isolated random
number generators (`random.Random(seed)`).

### Tests

Run DI2 tests:

```bash
python -m pytest test/test_sampling_algorithms.py -v

# DA1 – Identifier Analysis using srcML

## Overview
This assignment implements a small static analysis pipeline that extracts identifier-level information from source code using srcML and computes file-level naming and vocabulary metrics.

The system parses srcML XML, identifies functions, classes, parameters, and variables, and generates aggregate statistics describing naming conventions and identifier quality.

## Implementation
The following components were implemented:

- `extract_identifiers_dom()`  
  Parses srcML XML using ElementTree (DOM approach) and extracts identifier data.

- `aggregate_identifier_features()`  
  Computes file-level metrics including:
  - number of identifiers
  - average identifier length
  - token statistics
  - vocabulary size and diversity
  - naming convention percentages

- `build_file_identifier_dataset()`  
  Builds dataset rows from multiple files.

## Workflow
The main pipeline performs:

1. Repository mining using previous assignments.
2. Retrieval of file content from Git history.
3. Conversion of source code to srcML XML using `srcml_runner`.
4. Identifier extraction and aggregation.
5. Automatic dataset generation.

Run the program with:

```bash
python main.py .


##DA2 – Vocabulary Clustering, Alignment & Feature Engineering
Overview

**This assignment extracts, normalizes, and analyzes vocabulary from software repositories, integrating three text sources:**

Commit messages – what developers write about changes

Code identifiers – functions, classes, variables, parameters

Code comments – inline documentation

## Implementation
Components implemented in src/da2_vocabulary.py:

extract_comments_from_srcml() – extracts cleaned comment text from srcML XML
extract_vocabulary() – tokenizes and normalizes text
cluster_vocabulary() – k-means clustering on token embeddings
reduce_dimensions() – PCA or t-SNE for 2D visualization
visualize_clusters() – scatter plots of clusters
measure_alignment() – computes overlap metrics and cluster similarity
build_vocabulary_dataset() – integrates commits, identifiers, comments, clusters, and alignment metrics

## Workflow

The main pipeline in main.py performs:
Mine repository commits, identifiers, and comments
Normalize vocabulary for each source
Cluster tokens and reduce dimensions for visualization
Compute pairwise alignment between commits, identifiers, and comments

Generate output:
**Cluster scatter plots (commit_clusters.png, identifier_clusters.png, comment_clusters.png)**
**Alignment report (alignment_report.txt) with top tokens, cluster themes, and metrics**

## Run DI2 tests:

```bash
python -m pytest test/test_da2_vocabulary.py -v

## To generate output:
python main.py . --analyze 

##STRATA — M1: Modeling I (Commit Type Classification)

This assignment builds a supervised machine learning model to predict commit types from repository vocabulary features.

## Implementation

Components implemented in src/m1_modeling.py:

label_commit() – heuristic commit labeling

build_commit_features() – feature engineering using cluster fractions and vocabulary statistics

build_feature_matrix() – builds feature matrix and labels

split_dataset() – train/test split

train_classifier() – decision tree or random forest model

evaluate_model() – accuracy, classification report, confusion matrix

plot_feature_importance() – feature importance visualization

plot_confusion_matrix() – confusion matrix heatmap

load_commit_data() – loads commit messages from the database

## Run M1 Tests
python -m pytest test/test_m1_modeling.py -v

## Generate Output
python main.py . --predict
python main.py . --analyze --predict

