---
name: schema-audit
description: "Verifier skill. Audit domain schema for completeness, consistency, proper inheritance, and no redundancy. Report issues with severity, category, and fix suggestions."
---

# Schema Audit — Verifier: Schema Structure Audit

## Goal
Audit the domain schema for completeness, consistency, proper inheritance, and no redundancy.

## Verifier Instructions

You are the **Schema Auditor** (Codex verifier). Your task is to review the schema definition and identify issues.

### Audit Checklist

#### 1. Completeness
- Are all entity types from the user concerns covered?
- Are all required properties defined for each entity type?
- Are relationship types defined between entity types that should be connected?
- Are there entity types that appear in instances but are not defined in the schema?

#### 2. Consistency
- Do property names follow a consistent naming convention (snake_case)?
- Are property types consistent across the schema? (e.g., don't use "string" in one place and "str" in another)
- Are relationship types named consistently (UPPER_SNAKE_CASE)?
- Do entity type names use PascalCase?

#### 3. Inheritance
- Are parent entity types defined before child types?
- Do child types inherit all properties from parent types?
- Is there any circular inheritance?
- Is inheritance depth reasonable (max 3-4 levels)?

#### 4. No Redundancy
- Are there duplicate entity types with the same or similar names?
- Are there duplicate properties across entity types that should be inherited?
- Are there relationship types that are redundant (e.g., SUPPLIES and PROVIDES meaning the same thing)?

### Output Format
Report issues in a structured format:
```json
{
  "passed": false,
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "completeness|consistency|inheritance|redundancy",
      "description": "Description of the issue",
      "location": "entity_type: property or relationship",
      "suggestion": "How to fix the issue"
    }
  ],
  "summary": {
    "total_issues": 5,
    "errors": 2,
    "warnings": 2,
    "info": 1
  }
}
```

### Action
- If issues found, return the report to the main agent for fixing.
- If no issues, confirm schema is valid.

## Rubrics Integration (Issues #14, #15)

### Load Rubrics
Before auditing, load the strict rubrics that drive this skill:

```python
from auto_domain_kg.audit_rubrics import RubricsConfig

# Load custom rubrics (default location), falling back to strict defaults.
config = RubricsConfig.load_from_file("config/audit_rubrics.yaml")
# or: config = RubricsConfig.load_default()
```

### Strict Thresholds (default strict)
Apply these thresholds from the `schema_audit` rubric during the audit:
- `max_missing_entity_types = 0` — any entity type referenced by instances but undefined in the schema is an **error**.
- `max_undefined_relationships = 0` — any relationship type used without a schema definition is an **error**.

Under STRICT auditing: **any error-level issue blocks the round from passing**. Warnings are tracked but do not block.

### Structured Output for AuditReportGenerator
Each issue MUST carry a stable `id` (e.g. `SCHEMA-001`), `severity` (`error`|`warning`|`info`), `category`, `description`, `location`, and `suggestion`. The `summary` block must report `total_entity_types`, `missing_entity_types`, `undefined_relationships`, `errors`, and `warnings`. This dict is consumed directly by `auto_domain_kg.audit_report.AuditReportGenerator.generate_report()`.

### Report Generation
After auditing, hand the structured result to the main agent, which calls:
```python
from auto_domain_kg.audit_report import AuditReportGenerator, AuditHistory
generator = AuditReportGenerator()
# report = generator.generate_report(round_number, sub_reports, config, worker_fixes)
# generator.save_report(report, output_dir="reports/audits/")
# AuditHistory("reports/audits/").add_round(report)
```
Each round's audit report (markdown + JSON) is saved to `reports/audits/round_N/` and appended to `reports/audits/audit_history.jsonl` for full adversarial traceability.