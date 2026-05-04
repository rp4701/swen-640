# Commit Message Analysis Pipeline


This project analyzes the relationship between commit size and commit message descriptiveness using real-world Git repositories. It was developed as part of a research study to better understand developer behavior when writing commit messages.




# Overview

The pipeline performs the following steps:


Extraction of commit messages from Git repositories

Classification of commit messages

Statistical analysis

Research question evaluation

Visualization of results




# Research Questions


RQ1: Does commit size (number of files changed) correlate with commit message length?

RQ2: To what extent do commit messages reflect the actual files modified?




# Requirements


Python 3.8+

Git installed

Install dependencies:

pip install -r requirements.txt




# Setup Instructions


1. Clone the Repository
git clone <your-repo-url>
cd <your-repo-name>

2. Create Required Directory
After cloning, manually create a repos/ folder:
mkdir repos

This folder is used to store external repositories for analysis and is excluded from version control via .gitignore.




# Configure Repository Paths


The pipeline reads repositories from predefined paths.

Open the file:
analysis/extract_messages.py

Find:
repos = ["repos/react"]
Update it with the repositories you want to analyze:
repos = [
   "repos/react",
   "repos/your-repository"
]




# How to Run


Execute the pipeline in the following order:

python analysis/extract_messages.py
python analysis/commit_classifier.py
python analysis/rq1_analysis.py
python analysis/rq2_analysis.py
python analysis/insights.py
python analysis/visualization.py




# Output


All results are generated inside the output/ directory:

commit_messages.csv → Extracted commit messages
commit_summary.csv → Classified commit types
Statistical analysis results
Visualizations and graphs

