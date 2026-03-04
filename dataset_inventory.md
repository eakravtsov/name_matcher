# Dataset Inventory: name_matcher

This document provides a breakdown of the datasets currently ingested into the `names_kb.db` SQLite database.

## 1. carltonnorthern Nicknames
- **Source**: [carltonnorthern/nicknames](https://github.com/carltonnorthern/nicknames)
- **Description**: A hand-curated dataset of standard English given names and their common diminutives or nicknames (e.g., "Bill" for "William").
- **Relation Type**: `diminutive`
- **Stats**:
  - **Relations**: 5,106 (symmetric)
  - **Names Involved**: ~4,328 unique strings
- **Role**: Handles the majority of common English-root name-to-nickname mappings.

## 2. Wikidata P460 (Said to be the same as)
- **Source**: [Wikidata (via SPARQL)](https://query.wikidata.org/)
- **Description**: The [P460](https://www.wikidata.org/wiki/Property:P460) property ("said to be the same as") is an official Wikidata property used to link different items that refer to the same entity. In the context of names, it is used to connect cross-lingual equivalents and spelling variants (e.g., "John" vs. "Juan" or "George" vs. "Georgios").
- **Relation Type**: `translation`
- **Stats**:
  - **Relations**: 1,278 (symmetric)
  - **Names Involved**: ~1,438 unique strings
- **Role**: Provides authoritative cross-lingual and regional equivalents for European-root names.

---
*Generated: 2026-03-04*
