---
name: triple-extraction
description: "Extract entity-relation triples (subject, predicate, object) from collected news evidence. Save entities and relationships to markdown, save evidence slices with provenance to data/evidence/."
---

# Triple Extraction — Step 3c: Extract Entity-Relation-Entity Triples

## Goal
Extract (entity, relation, entity) triples with evidence slices from collected news articles and save them for graph persistence.

## Weak Agent Instructions

You are a **Triple Extractor** (weak agent). Your task is to extract structured triples from the collected evidence.

### Process

1. **Load the schema** from `tmp/schema_definition.json`.
2. **Load evidence** from `data/evidence/` using the `EvidenceStore`.
3. **For each evidence record**, extract triples:

   ```
   (Entity A) --[RELATIONSHIP]--> (Entity B)
   ```

   Example:
   ```
   (Apple Inc.) --[SUPPLIES]--> (iPhone Processors)
   Evidence: "Apple contracts with TSMC to manufacture iPhone processors"
   ```

4. **Validate triples against the schema**:
   - Entity A and Entity B should match defined entity types
   - Relationship should be a defined relationship type
   - If a triple doesn't match the schema, flag it for schema refinement

5. **Save extracted triples** to `tmp/extracted_triples.md`:

   ```markdown
   ## Triple: [ID-001]
   - **Subject**: Apple Inc. (entity_type: Company)
   - **Relation**: SUPPLIES
   - **Object**: iPhone Processors (entity_type: Product)
   - **Evidence**: "Apple contracts with TSMC to manufacture iPhone processors"
   - **Source**: https://example.com/news/1
   - **Confidence**: HIGH
   ```

6. **Save evidence for each triple**:
   - Use `EvidenceStore.save_evidence()` with relation_id set
   - Each triple gets a unique relation_id

### Extraction Guidelines
- **Prefer explicit statements** over inferred relationships
- **Include exact text** from the source as evidence
- **Confidence levels**: HIGH (explicitly stated), MEDIUM (strongly implied), LOW (weakly inferred)
- **One triple per row** — do not combine multiple relationships
- **Entity names** should be as specific as possible
- **Date context**: Include publication date if relevant

### Quality Checks
- Skip triples with vague or ambiguous entities
- Flag contradictory triples from different sources
- Note if a triple is time-sensitive (e.g., "CEO of Company X as of 2024")