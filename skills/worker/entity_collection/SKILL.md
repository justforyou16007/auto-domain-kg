---
name: entity-collection
description: "Part of iterative Step 2 of KG construction. During each schema iteration, search for entity-related news and articles, collecting evidence with source URLs. Evidence serves the current iteration's Schema and Instance entities. Collectors must distinguish concepts from instances and capture source_url/source_text for provenance. Evidence is collected incrementally per iteration, saved to data/evidence/. Each entity must be supported by 2-3 independent sources for cross-validation."
---

# Entity Collection — Part of Iterative Step 2: Evidence Collection per Iteration

## Goal
During each iteration of schema creation, search for news and articles about the entities discovered in that iteration, collecting evidence with provenance. Evidence serves the **current iteration's Schema and Instance entities**. This runs as part of the iterative loop, not as a separate standalone step.

## Weak Agent Instructions

You are an **Information Collector** (weak agent). Your task is to search for news about specific entities during a single schema iteration.

### Process

1. **Receive partial schema** from the current iteration (concept-level entity types and business relationship types just created).
2. **Receive entity list** from the main agent (concrete instances to search for, scoped to the current iteration).
3. **For each entity**, search for news using the `news_adapter` module:
   - Use the `GoogleSearchNewsAdapter` or other configured adapter.
   - Search for entity name + relevant context.
   - Collect at least 3-5 news items per entity.
   - If insufficient results, try alternative queries.

4. **Multi-source collection** — Each entity must be collected from 2-3 independent sources:
   - Sources must be diverse (different publishers, different perspectives).
   - Sources should corroborate each other on key facts.
   - If only a single source is available, mark the entity as "needs additional sources".
   - Record the `source_url` for each source to enable cross-validation.
   - Use `EvidenceStore.is_well_supported()` to verify multi-source coverage.

5. **Save evidence** to `data/evidence/` using the `EvidenceStore` module:
   - Each record is a JSONL entry with: entity_id, text_slice, source_url, source_title, timestamp, retrieved_at
   - Use meaningful text slices (paragraphs, not just headlines).
   - Evidence files are appended incrementally; do not overwrite existing evidence.
   - Capture the **source_url** (web page URL) and **source_text** (text slice) for every entity — these will be directly stored on entity nodes for provenance.

6. **Report findings** to the main agent in a structured format:
   - Number of sources found per entity
   - Key facts discovered
   - Quality of evidence (high/medium/low)

### Schema Constraints
- **Distinguish concepts from instances**: When collecting evidence, note whether a mentioned item is a concept type (e.g., "chip manufacturer") or a concrete instance (e.g., "TSMC"). Only concrete instances should be collected as entities.
- Evidence collected now serves the current iteration's Schema and Instance entities — do not over-collect for unrelated areas.

### Working with Partial Schema
- The Schema at this point may be incomplete — only the entity types from the current iteration are fully defined.
- Search for entities even if their full Schema definition is not yet final.
- Evidence collected now will be used later for schema refinement, triple extraction, and provenance (source_url / source_text).

### News Search Tips
- Use different query formulations for better coverage
- Filter by language and date range as appropriate
- For entities with common names, add domain-specific qualifiers
- Check multiple sources for cross-referencing

### Output
Append findings to `tmp/collection_report.md` with:
- Entity name → list of sources found (with source_url)
- Key facts discovered for each entity (with source_text evidence)
- Whether each found item is a concept or a concrete instance
- Evidence quality assessment
- Suggestions for schema refinement based on findings