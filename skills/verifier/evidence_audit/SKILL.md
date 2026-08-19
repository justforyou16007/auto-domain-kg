---
name: evidence-audit
description: "Verifier skill. Audit entity and relationship evidence for multi-source consistency. Verify that evidence slices match source URLs and that facts are corroborated across sources."
---

# Evidence Audit — Verifier: Entity/Relation Evidence Audit

## Goal
Audit entity and relationship evidence for multi-source consistency, evidence quality, and ensure no single-source-only facts.

## Verifier Instructions

You are the **Evidence Auditor** (Codex verifier). Your task is to review the evidence backing each entity and relationship in the graph.

### Audit Checklist

#### 1. Multi-Source Consistency
- For each important fact, are there at least 2 independent sources?
- Do the sources agree on the fact? (If sources disagree, flag as conflicting)
- Are the sources diverse (different publishers, perspectives)?
- Check if multiple sources are from the same parent organization.

#### 2. Evidence Quality
- Is the evidence text a meaningful slice (not just a headline)?
- Does the evidence directly support the entity/relationship it's attached to?
- Is the source URL accessible and credible?
- Is the source title descriptive?
- Is the timestamp present and reasonable?

#### 3. No Single-Source-Only Facts
- Identity facts (entity name, type) can be single-source.
- Relational facts (Entity A --[RELATES]--> Entity B) should have at least 2 sources.
- Critical facts (risk events, major changes) should have 3+ sources.

#### 4. Evidence Provenance
- Is the `retrieved_at` timestamp present?
- Is the source URL valid (not a 404 or error page)?
- Is the text slice large enough to provide context (minimum 50 chars)?

### Process
1. Load evidence for each entity using `EvidenceStore.load_evidence_by_entity(entity_id)`.
2. Load evidence for each relationship using `EvidenceStore.load_evidence_by_relation(relation_id)`.
3. Count sources per entity/relation.
4. Check for conflicting evidence.
5. Assess evidence quality.

### Output Format
```json
{
  "passed": false,
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "single_source|conflicting|quality|provenance",
      "entity_id": "entity_or_relation_id",
      "description": "Description of the evidence issue",
      "source_count": 1,
      "suggestion": "How to fix"
    }
  ],
  "summary": {
    "total_entities_audited": 0,
    "total_relations_audited": 0,
    "single_source_entities": 0,
    "single_source_relations": 0,
    "conflicting_evidence": 0,
    "quality_issues": 0
  }
}
```