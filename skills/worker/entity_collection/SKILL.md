---
name: entity-collection
description: "Part of iterative Step 2 of KG construction. During each schema iteration, search for entity-related news and articles, collecting evidence with source URLs. Evidence is collected incrementally per iteration, saved to data/evidence/."
---

# Entity Collection — Part of Iterative Step 2: Evidence Collection per Iteration

## Goal
During each iteration of schema creation, search for news and articles about the entities discovered in that iteration, collecting evidence with provenance. This runs as part of the iterative loop, not as a separate standalone step.

## Weak Agent Instructions

You are an **Information Collector** (weak agent). Your task is to search for news about specific entities during a single schema iteration.

### Process

1. **Receive partial schema** from the current iteration (entity types and relationship types just created).
2. **Receive entity list** from the main agent (entities to search for, scoped to the current iteration).
3. **For each entity**, search for news using the `news_adapter` module:
   - Use the `GoogleSearchNewsAdapter` or other configured adapter.
   - Search for entity name + relevant context.
   - Collect at least 3-5 news items per entity.
   - If insufficient results, try alternative queries.

4. **Save evidence** to `data/evidence/` using the `EvidenceStore` module:
   - Each record is a JSONL entry with: entity_id, text_slice, source_url, source_title, timestamp, retrieved_at
   - Use meaningful text slices (paragraphs, not just headlines).
   - Evidence files are appended incrementally; do not overwrite existing evidence.

5. **Report findings** to the main agent in a structured format:
   - Number of sources found per entity
   - Key facts discovered
   - Quality of evidence (high/medium/low)

### Working with Partial Schema
- The schema at this point may be incomplete — only the entity types from the current iteration are fully defined.
- Search for entities even if their full schema definition is not yet final.
- Evidence collected now will be used later for schema refinement and triple extraction.

### News Search Tips
- Use different query formulations for better coverage
- Filter by language and date range as appropriate
- For entities with common names, add domain-specific qualifiers
- Check multiple sources for cross-referencing

### Output
Append findings to `tmp/collection_report.md` with:
- Entity name → list of sources found
- Key facts discovered for each entity
- Evidence quality assessment
- Suggestions for schema refinement based on findings