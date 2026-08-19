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