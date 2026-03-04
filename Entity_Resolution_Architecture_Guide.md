# Entity Resolution System: Comprehensive Deep-Dive Architecture Guide

This guide provides an exhaustive, granular breakdown of the **Multi-Tier Entity Resolution Engine**. It is designed for maximum technical depth, specifically intended for ingestion by Large Language Models (LLMs) and tools like Google NotebookLM to synthesize study guides, API documentation, and architectural summaries.

---

## 1. System Philosophy and The "Three-Tiered" Paradigm

The engine rejects the notion that a single algorithm can solve human name matching. Instead, it employs a **Multi-Tiered, Hybrid Pipeline**. It uses the absolute determinism of curated dictionaries (Knowledge Bases) for known entities, falling back gracefully to the fuzzy, associative logic of Deep Learning for typos and rare names, and orchestrates everything through a combinatorial graph-theory algorithm for multi-token names.

The core pipeline evaluates pairs of entities through three sequential levels:
1.  **L1 (Level 1 Router):** The deterministic Knowledge Base and strict rules engine.
2.  **L2 (Level 2 Inference):** The PyTorch Character-Level Siamese Neural Network.
3.  **L3 (Level 3 Orchestrator):** The Compound Resolution Matrix utilizing Graph Theory.

---

## 2. Level 1 (L1) Router: The Knowledge Base Engine

The L1 Router is the first line of defense and the fastest component of the system. It connects to a highly optimized SQLite database (`names_kb.db`) that stores millions of curated human relationships.

### 2.1 The Core Dictionaries (Tables)
The database structure is built on two primary tables:
*   `names`: Contains single-token names, their linguistic origin, and their assigned gender (`M`, `F`, `U`nknown).
*   `relationships`: Maps an `entity_a` to an `entity_b`, categorizing the type of connection and its source dataset.

### 2.2 Relationship Types
The system categorizes name connections explicitly to understand *why* two names match:
*   **Translation (Alias):** Cross-lingual identicals (e.g., `Alexander` -> `Alejandro`). Scored at 100%.
*   **Diminutive (Nickname):** Highly irregular shortenings (e.g., `Richard` -> `Dick`, `Elizabeth` -> `Bessie`). Scored at 100% because phonetic algorithms fail drastically on these.
*   **Mismatch (False Positive):** Explicit definitions that two names do NOT match, despite visual similarity (e.g., `Samuel` != `Samantha`). Scored at 0%.

### 2.3 The Graph Transitivity Engine (Hop Traversals)
L1 doesn't just look for direct A-to-B mappings; it treats the database as an undirected graph.
*   **The Problem:** The database knows `John` -> `Johnny` and `Johnny` -> `Jon`, but doesn't explicitly have a row for `John` -> `Jon`.
*   **The Solution:** The L1 Router uses Breadth-First Search (BFS) to traverse the relationship graph. It allows for multi-hop connections, discovering that `John` is linked to `Jon` via a shared neighbor. This exponentially increases the power of the clean underlying data without requiring $N \times N$ explicit rows.

### 2.4 The Nuclear Veto: Strict Gender Enforcement
Names that look similar are often the most dangerous false positives. 
*   **The Logic:** If L1 detects that Token A is definitively Male (`M`) and Token B is definitively Female (`F`), it permanently vetoes the match, returning a 0% score and terminating further analysis. 
*   **The Exception (Unisex):** If either name is categorized as Unknown (`U`) or if both share the same gender, the veto is bypassed.

### 2.5 Strict Unknowns (Toggle Feature)
A toggleable guardrail against deep-learning hallucinations on extremely rare or misspelled data.
*   **The Logic:** When the **"Strict Unknowns" toggle is ON**, the router checks if either Token A or Token B is actively listed in the `names` table of the Knowledge Base. 
*   **The Trigger:** If a token is completely unknown to the system (i.e., not a single record exists for it), the router forces an exact 1:1 spelling match requirement. If the orthography isn't an exact match, it rejects the pair immediately (0%).
*   **The Purpose:** It prevents the neural network from trying to find "fuzzy" phonetic similarities between random strings or exceptionally obscure data where the margin for error is unacceptable. When **OFF**, unknown words are passed to the L2 Siamese Network to estimate their typographical closeness.

---

## 3. Level 2 (L2) Inference: PyTorch Siamese Neural Network

If the L1 Router cannot find a definitive connection (either an approval or a veto), the single-token pair is handed off to the deep learning engine.

### 3.1 Why a Character-Level Siamese Architecture?
*   **Character-Level Recurrent Neural Network (GRU):** The network does not look at whole words as embeddings (like Word2Vec or BERT). It processes names character-by-character. It learns that the sequence `S-M-I-T-H` is functionally similar to `S-M-Y-T-H-E` because it was trained to ignore common vowel substitutions and double-consonant drops.
*   **The Siamese Twin Structure:** The neural network is actually two identical "twin" networks sharing the exact same weights. Token A is fed into Twin 1; Token B is fed into Twin 2.

### 3.2 Embedding Generation & Contrastive Loss
*   Each twin processes its character string (converted into tensors corresponding to A-Z, spaces, hyphens) and outputs a dense vector (an Embedding) representing that string in high-dimensional mathematical space.
*   **Training via Contrastive Loss:** During training, the system was fed millions of positive pairs (matching names with synthetic typos generated by `generate_data.py`) and negative pairs (distinctly different names). Contrastive Loss pulls the vectors of positive pairs close together while pushing negative pairs far apart (enforcing a configured "margin" of separation).

### 3.3 Confidence Scoring via Cosine Similarity
*   When evaluating a live pair, the L2 Engine calculates the **Cosine Similarity** between Embedding Vector A and Embedding Vector B. 
*   A Cosine Similarity of `1.0` means the vectors point in the exact same direction (perfect match). The score is mapped to a percentage (e.g., a similarity of `0.95` becomes a `95.0%` confidence match).

---

## 4. Level 3 (L3) Orchestrator: The Compound Matching Matrix

Human names are rarely evaluated as isolated, single tokens. They are compounds: First Names, Middle Names, Surnames, Titles, and Suffixes. L3 is the architectural layer that resolves these complex multi-token identities (e.g., `Mr. John R. Tolkien` vs. `Tolkien, John Ronald Reuel`).

### 4.1 Tokenization and Sanitization
Before matching, the raw input strings undergo rigorous cleaning:
1.  **Lowercasing:** Case is neutralized.
2.  **Punctuation Stripping:** Commas, periods, and hyphens are removed (e.g., `O'Connor` becomes `Oconnor`, `T-Bone` becomes `Tbone`).
3.  **Token Splitting:** The strings are split by whitespace into two distinct arrays of tokens: Array A and Array B.

### 4.2 The Bipartite Graph & The Hungarian Algorithm
How does the system know which word in String A corresponds to which word in String B, especially if they are out of order? It uses Graph Theory.

*   **Matrix Construction:** The engine builds a 2D Matrix (a grid) where the rows are tokens from Array A, and the columns are tokens from Array B.
*   **Cell Population:** It iteratively evaluates every token in A against every token in B using the L1/L2 pipeline described above. It fills every cell in the grid with a percentage confidence score. 
*   **The Hungarian Algorithm (Linear Sum Assignment):** It applies this classic optimization algorithm (provided by `scipy.optimize.linear_sum_assignment`) to the matrix to find the "Maximum Weight Matching" in a bipartite graph. In simple terms: it finds the absolute best combination of token alignments that maximizes the total score, ensuring no word is used twice.

### 4.3 Combinatorial Features and Toggles
L3 behavior is highly mutable via user toggles to accommodate different compliance risk appetites:

#### 4.3.1 Symmetrical vs. Asymmetrical Strategy
*   **Symmetrical (Strict):** Evaluates how completely identical the two entities are as a whole.
    *   *Math:* It takes the sum of the best matching token scores and divides by the total number of tokens in the *longer* string. (`max(len(A), len(B))`)
    *   *Result:* "John" vs. "John Smith" will score poorly (~50%), because "Smith" is completely unmatched and penalizes the score.
*   **Asymmetrical (Loose/Containment):** Evaluates whether Entity A is completely *contained* within Entity B.
    *   *Math:* It divides the total matched score by the total number of tokens in the *shorter* string. (`min(len(A), len(B))`)
    *   *Result:* "John" vs. "John Smith" will score functionally at 100%, because "John" fully aligns with the "John" inside "John Smith."

#### 4.3.2 Enforce Strict Order
*   **Logic When OFF (Default):** The Hungarian algorithm searches the entire matrix unconditionally. "Muhammad Ali" perfectly aligns with "Ali Muhammad" because both words exist on both sides, and order doesn't matter.
*   **Logic When ON:** The system heavily penalizes or forbids alignments if a token from the beginning of String A aligns to a token at the end of String B. It enforces that sequences must match linearly (Subject -> Object).

#### 4.3.3 Allow Initials
*   **Logic When OFF (Default):** A single letter 'J' compared against 'John' will be treated as a massive orthographic failure by the L2 neural engine and score near 0%.
*   **Logic When ON:** The L3 orchestrator intercepts single-character tokens during Matrix construction. If Token A is 'J' and Token B is 'John', and the first letter of Token B matches the initial exactly ('j' == 'j'), the system forcefully injects a 1.0 (100%) confidence score into that specific matrix cell. This enables near-perfect matching for cases like `J.R.R. Tolkien` to `John Ronald Reuel Tolkien`, assuming the rest of the name aligns via the Hungarian algorithm.

---

## 5. UI and Knowledge Base Feedback Loop
The frontend dashboard provides a real-time, side-by-side analysis surface. The critical architectural feature here is the **Knowledge Base Override Tool**, located directly beneath the analysis trace.

### 5.1 The Real-Time Learning Loop
If the L2 Neural Engine hallucinates a high score for two words that look similar but *should* definitively fail (e.g., an obscure regional dispute), the user can inject an explicit `mismatch` rule via the UI directly into the L1 SQLite database (`names_kb.db`). 

Because the L1 Router runs *before* the L2 Neural Network, this creates an immediate, overriding feedback loop. The very next time the engine evaluates those entities, the L1 Router intercepts the call, reads the new veto rule, and violently rejects the match with 0% confidence before the neural network is even engaged. This empowers users to correct edge cases instantly without retraining the underlying Siamesemodel.
