# Audit Report — Round {{ round_number }}

- **Timestamp**: `{{ timestamp }}`
- **Overall**: {{ overall_status }}
- **Total issues**: {{ total_issues }}
- **Errors**: {{ errors }}
- **Warnings**: {{ warnings }}

## Rubrics Applied

| Rubric | Strictness | Enabled | Thresholds |
|--------|------------|---------|------------|
{{ rubrics_table }}

## Schema Audit

- Passed: {{ schema_passed }}
- Total entity types: {{ schema_total_entity_types }}
- Missing entity types: {{ schema_missing_entity_types }}
- Undefined relationships: {{ schema_undefined_relationships }}

## Graph Structure Audit (Connectivity Metrics)

- Passed: {{ graph_passed }}
- Total entities: {{ graph_total_entities }}
- Orphan entities: {{ graph_orphan_entities }}
- Avg relationships per entity: {{ graph_avg_relationships }}

## GraphRAG Validation (Question Results)

- Passed: {{ graphrag_passed }}
- Total questions: {{ graphrag_total_questions }}
- Answerable: {{ graphrag_answerable }}
- Unanswerable: {{ graphrag_unanswerable }}

| Question | Answerable | Precision | Results |
|----------|------------|-----------|---------|
{{ graphrag_questions_table }}

## Evidence Audit (Source Counts)

- Passed: {{ evidence_passed }}
- Entities audited: {{ evidence_entities_audited }}
- Single-source entities: {{ evidence_single_source }}
- Conflicting evidence: {{ evidence_conflicting }}

## Task Relevance Audit (Coverage)

- Passed: {{ relevance_passed }}
- Total concerns: {{ relevance_total_concerns }}
- Fully covered: {{ relevance_fully_covered }}
- Partially covered: {{ relevance_partially_covered }}
- Not covered: {{ relevance_not_covered }}
- Fully-covered ratio: {{ relevance_fully_covered_ratio }}

## Issue Breakdown

- Errors: {{ errors }} | Warnings: {{ warnings }} | Total: {{ total_issues }}

| Severity | Audit | Category | Issue ID | Description |
|----------|-------|----------|----------|-------------|
{{ issues_table }}

## Worker Fixes (Traceability)

| Fix | Issue IDs Addressed | Files Modified |
|-----|----------------------|----------------|
{{ worker_fixes_table }}

## Summary

{{ summary }}
