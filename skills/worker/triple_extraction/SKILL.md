---
name: triple-extraction
description: "Step 3c: Extract entity-relation triples (subject, predicate, object) from collected news evidence, guided by the Schema layer. Only extract concrete Instance entities (never concepts). Validate Instance relationships against Schema-to-Schema relationships. Each entity records source_url and source_text. Save entities and relationships to markdown, save evidence slices with provenance to data/evidence/."
---

# Triple Extraction — Step 3c: Extract Entity-Relation-Entity Triples (Instance Layer)

## Goal
Extract (entity, relation, entity) triples with evidence slices from collected news articles. Extraction is **guided by the Schema layer**: it only extracts concrete **Instance-level** entities, and validates entity relationships against the Schema's relationship types.

## Weak Agent Instructions

You are a **Triple Extractor** (weak agent). Your task is to extract structured triples from the collected evidence, guided by the Schema constraints.

### Input
- Schema from `tmp/schema_definition.json` (concept-level entity types + relationship types)
- Evidence from `data/evidence/` (loaded via `EvidenceStore`)
- User concerns from `CLAUDE.md`

### Process

1. **Load the Schema** from `tmp/schema_definition.json`.
2. **Load evidence** from `data/evidence/` using the `EvidenceStore`.
3. **For each evidence record**, extract triples:

   ```
   (Entity A) --[RELATIONSHIP]--> (Entity B)
   ```

   Example:
   ```
   (TSMC) --[SUPPLIES]--> (iPhone Processors)
   Evidence: "Apple contracts with TSMC to manufacture iPhone processors"
   ```

4. **Map entities to Schema types**:
   - Each concrete Instance entity must map to exactly one Schema entity type.
   - Only extract **concrete instances** (e.g., "TSMC", "Xiaomi SU7", "Sigma 50mm F1.4"). Do NOT extract concept names (e.g., "chip manufacturer", "car") as entities.
   - If an entity is a concept rather than an instance, skip it (or record it for the Schema layer).

5. **Validate triples against Schema relationships**:
   - Check whether the two entities' Schema types have a defined relationship between them.
   - **Valid**: Schema A and Schema B have a defined relationship type, and the Instance A→Instance B relationship uses that type.
     - Example: `Supplier` ―[`SUPPLIES`]→ `Material` exists in Schema, so `TSMC` ―[`SUPPLIES`]→ `Silicon Wafers` is valid.
   - **Schema inconsistency**: Schema A and Schema B have a relationship type, but the Instance relationship uses a different/wrong type. Mark it and flag.
   - **Schema extension needed**: Instance A and Instance B have a genuine relationship, but Schema A and Schema B have NO defined relationship. Mark it as a Schema extension requirement.

6. **Record source_url and source_text for every entity**:
   - Each entity node must record `source_url` (the originating web page URL) and `source_text` (the exact evidence text slice) so it can be traced back to its source.
   - These come from the extraction phase's evidence records.

7. **Save extracted triples** to `tmp/extracted_triples.md`:

   ```markdown
   ## Triple: [ID-001]
   - **Subject**: TSMC (entity_type: Supplier, schema: Supplier)
   - **Relation**: SUPPLIES
   - **Object**: Silicon Wafers (entity_type: Material, schema: Material)
   - **Evidence**: "Apple contracts with TSMC to manufacture iPhone processors"
   - **Source**: https://example.com/news/1
   - **Source URL**: https://example.com/news/1
   - **Source Text**: "Apple contracts with TSMC to manufacture iPhone processors"
   - **Confidence**: HIGH
   ```

8. **Save evidence for each triple**:
   - Use `EvidenceStore.save_evidence()` with relation_id set
   - Each triple gets a unique relation_id

### Extraction Guidelines
- **Prefer explicit statements** over inferred relationships
- **Include exact text** from the source as evidence
- **Confidence levels**: HIGH (explicitly stated), MEDIUM (strongly implied), LOW (weakly inferred)
- **One triple per row** — do not combine multiple relationships
- **Entity names** should be specific concrete instances (never concept names)
- **Integer with Schema**: Every entity belongs to a defined Schema type
- **Source provenance**: Record `source_url` and `source_text` for every entity
- **Date context**: Include publication date if relevant

### Schema Consistency & Completeness Checks
- **Missing connections**: Note if an entity would logically connect to others but no relationship evidence was found. Mark the missing connection for completeness exploration.
- **Schema extension needs**: If an Instance relationship has no matching Schema relationship, record it as a Schema extension requirement (do NOT silently drop it).
- **Schema inconsistency**: If an Instance relationship violates a Schema constraint, flag it as schema inconsistency.

### Completeness Awareness
When extracting, pay attention to whether the entity relationships are complete:
- Are there entities mentioned in the evidence that should be connected but have no relationship?
- Are there relationship types in the Schema that no instance uses yet?
- Report these gaps for the completeness exploration step.

### Quality Checks
- Skip triples with vague or ambiguous entities
- Flag contradictory triples from different sources
- Note if a triple is time-sensitive (e.g., "CEO of Company X as of 2024")
- Every entity must have a valid Schema type mapping
- Every entity must have source_url and source_text