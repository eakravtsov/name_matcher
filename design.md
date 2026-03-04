# System Design Document: Compute-Sipping Name Entity Resolution

**Objective:** Build a multi-tier, highly efficient entity resolution pipeline for European-root names that outputs calibrated confidence intervals and human-readable explanations, supporting both `conservative` and `liberal` matching strategies.

## Phase 1: The Mega-Dictionary (Level 1)
**Goal:** Build a SQLite database to handle 90%+ of canonical matches and strict vetoes with O(1) complexity.

* **Task 1.1: Database Schema Creation**
    * Initialize a SQLite database (`names_kb.db`).
    * Create tables: 
        * `CanonicalNames` (id, name_string)
        * `NameRelations` (source_id, target_id, relation_type, confidence, context)
    * *Relation Types:* `translation`, `diminutive`, `spelling_variant`.
* **Task 1.2: Data Ingestion Scripts**
    * Write a Python script to download and parse the `carltonnorthern` nicknames CSV.
    * Write a SPARQL script to fetch cross-lingual links (e.g., Greek to English) from Wikidata.
    * Populate the SQLite database, ensuring relationships are symmetric (e.g., Bill <-> William).
* **Task 1.3: The Level 1 Router**
    * Write a function `check_level_1(name1, name2, mode)` that normalizes text (using `unidecode` and lowercasing) and queries the SQLite DB.
    * Implement the **Veto Logic**: If both names exist in `CanonicalNames` but have no record in `NameRelations`, return a strict `NO_MATCH` flag (subject to `mode` overrides).

## Phase 2: Data Generation & Hard Negatives
**Goal:** Create the training and validation datasets for the neural network, explicitly teaching it to avoid common pitfalls.

* **Task 2.1: Positive Pair Generation**
    * Sample valid pairs from the SQLite database.
    * Generate synthetic positive pairs by injecting standard string typos (character swap, drop, insert) into known names.
* **Task 2.2: Negative Pair Generation (Crucial)**
    * *Easy Negatives:* Pair completely different strings of different lengths (e.g., `George` / `Alexander`).
    * *Hard Negatives:* Pair names that are 1-2 characters apart but mathematically distinct entities (e.g., `Maria` / `Mario`, `Oliver` / `Olivia`, `Lee` / `Les`).
* **Task 2.3: Train/Val Split**
    * Output the generated dataset into `train.csv` and `val.csv` with a boolean `is_match` label.

## Phase 3: The Neural Fallback & Calibrator (Levels 2 & 3)
**Goal:** Train a lightweight character-level model and a statistical calibrator.

* **Task 3.1: Siamese Network Architecture**
    * Using PyTorch, define a `SiameseCharCNN` or `SiameseCharLSTM`.
    * Input: Character vocabulary indices (padded to a max length of 20).
    * Loss Function: `CosineEmbeddingLoss` or `ContrastiveLoss`.
* **Task 3.2: Training Loop**
    * Train the model on `train.csv`. Ensure the loss metric accurately pushes Hard Negatives apart.
    * Save the model weights (`siamese_model.pt`).
* **Task 3.3: Platt Scaling (Calibration)**
    * Run `val.csv` through the trained PyTorch model to get raw distance scores.
    * Train a `LogisticRegression` model from `scikit-learn` on these raw scores against the true labels.
    * Save the calibrator (`calibrator.pkl`). This model will convert raw distances to a `0.0` to `1.0` probability.

## Phase 4: The Explanation Engine & API (Level 4)
**Goal:** Wrap the pipeline in a single, user-facing Python class with strategic toggles.

* **Task 4.1: QWERTY Distance Utility**
    * Write a helper function to calculate keyboard spatial distance to assess if a 1-character difference is likely a typo.
* **Task 4.2: The Main Wrapper (`NameMatcher` class)**
    * Implement `evaluate(name1, name2, mode="conservative")`.
    * **Conservative Mode Logic:** Enforce strict Level 1 vetoes. Require >95% confidence from Level 3.
    * **Liberal Mode Logic:** Override Level 1 vetoes if Levenshtein distance is <= 1. Boost Level 3 scores using the QWERTY utility. Lower threshold to >60%.
* **Task 4.3: Explanation Formatting**
    * Return a dictionary: `{"match": bool, "confidence": float, "explanation": str}`.
    * Write conditional string formatting based on whether the match triggered Level 1 (e.g., "Greek variant") or Level 2 ("Likely typo").