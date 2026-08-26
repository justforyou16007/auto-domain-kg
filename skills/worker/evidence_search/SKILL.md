---
name: evidence-search
description: "Step 4a of the KG pipeline. Deep-research-style evidence search. Multi-round iterative: each round generates zh+en queries → bilingual_search() top-k=20 → merge by URL → translate_content() to zh-CN → analyze findings → generate next-round questions → continue. Does NOT stop after finding one piece of evidence — goal is comprehensive coverage. Stop when a round produces no new facts. Uses news_adapter.bilingual_search() and translation.TranslationClient.translate_content(). Saves evidence to data/evidence/."
---

# Evidence Search — Step 4a: Deep-Research-Style Multi-Round Evidence Collection

## Goal
Collect **comprehensive** evidence for a single Schema/Relation dimension using
a deep-research methodology. This is NOT a "find one source and stop" search —
the goal is broad coverage so downstream triple extraction has enough
corroborating material. Stop only when a search round produces no new facts.

## Input
- The Schema/Relation dimension assigned to this sub-agent (entity types +
  relationship types from `tmp/schema_definition.json`).
- User concerns from `CLAUDE.md`.
- Existing evidence in `data/evidence/` (to avoid re-collecting).

## Process

### Round Structure (iterate)
Each round performs the full cycle below. Rounds continue until the stop
condition is met.

#### 1. Generate Bilingual Queries
- For the current sub-topic, generate **both** a Chinese query and an English
  query. Use domain-specific phrasing in each language for better coverage.

#### 2. Bilingual Search
- Call `news_adapter.bilingual_search(query, english_query=..., max_results=20)`
  (top-k=20 per language).
- The adapter issues searches for both language queries, merges the results,
  and **deduplicates by URL**.

#### 3. Translate
- Translate every result to the working language (default `zh-CN`) via
  `translation.TranslationClient.translate_content()` /
  `translate_news_item()`. Each translated item carries `original_language`.

#### 4. Analyze Findings
- Extract the new facts/entities/relationships discovered this round.
- Record which facts are already known (from previous rounds or existing
  evidence) vs. genuinely new.

#### 5. Generate Next-Round Questions
- Based on the current findings and remaining gaps, formulate the next round's
  zh + en queries. Probe adjacent aspects, missing entities, and unverified
  relationships — do not just re-issue the same query.

#### 6. Continue
- Loop back to step 1 with the new queries.

### Stop Condition
Stop when a round produces **no new facts** — i.e. every finding is already
covered by previously collected evidence. Do NOT stop after finding a single
piece of evidence; comprehensive coverage is the goal.

## Multi-Source Cross-Validation
- Each entity/relation should be supported by 2-3 independent sources.
- Use `EvidenceStore.is_well_supported()` to verify multi-source coverage.
- Flag single-source facts as "needs additional sources".

## Saving Evidence
- Save evidence to `data/evidence/` using the `EvidenceStore` module as JSONL.
- Each record includes: entity_id, text_slice, source_url, source_title,
  timestamp, retrieved_at.
- Capture `source_url` (web page URL) and `source_text` (text slice) for every
  entity — these are stored on entity nodes for provenance.
- Append incrementally; do not overwrite existing evidence.

## Output
- `data/evidence/*.jsonl` — collected evidence with provenance.
- A round-by-round summary appended to `tmp/evidence_search_log.md`:
  - Queries used each round (zh + en).
  - New facts discovered each round.
  - When the stop condition was met.
