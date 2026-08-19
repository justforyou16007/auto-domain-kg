---
name: entity-collection
description: "Step 3 of KG construction. Spawn multiple weak sub-agents to search for entity-related news and articles, collecting evidence with source URLs for triple extraction."
---

# Entity Collection — Step 3: News/Evidence Collection for Entities

## Goal
Search for news and articles about the entities defined in the schema, collecting evidence with provenance.

## Weak Agent Instructions

You are an **Information Collector** (weak agent). Your task is to search for news about specific entities.

### Process

1. **Load the schema** from `tmp/schema_definition.json` to understand entity types.
2. **Receive entity list** from the main agent (entities to search for).
3. **For each entity**, search for news using the `news_adapter` module:
   - Use the `GoogleSearchNewsAdapter` or other configured adapter.
   - Search for entity name + relevant context.
   - Collect at least 3-5 news items per entity.
   - If insufficient results, try alternative queries.

4. **Save evidence** to `data/evidence/` using the `EvidenceStore` module:
   - Each record is a JSONL entry with: entity_id, text_slice, source_url, source_title, timestamp, retrieved_at
   - Use meaningful text slices (paragraphs, not just headlines).

5. **Report findings** to the main agent in a structured format:
   - Number of sources found per entity
   - Key facts discovered
   - Quality of evidence (high/medium/low)

### News Search Tips
- Use different query formulations for better coverage
- Filter by language and date range as appropriate
- For entities with common names, add domain-specific qualifiers
- Check multiple sources for cross-referencing

### Output
Save a report to `tmp/collection_report.md` with:
- Entity name → list of sources found
- Key facts discovered for each entity
- Evidence quality assessment
- Suggestions for schema refinement based on findings