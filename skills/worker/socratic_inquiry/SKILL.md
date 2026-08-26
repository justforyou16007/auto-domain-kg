---
name: socratic-inquiry
description: "Step 1 of KG construction. Ask a small number of Socratic questions to capture the user's domain, primary task, approximate entity/relationship types, and risk concerns. The user does NOT need to provide a detailed Schema — Schema is discovered through exploration in Step 2, not fixed at setup time. Save results to CLAUDE.md."
---

# Socratic Inquiry — Step 1: Extract User Concerns

## Goal
Understand what the user wants from the knowledge graph by asking a **small number** of high-level Socratic questions. Keep the setup lightweight and user-friendly — the detailed Schema, entities, and relationships are *discovered* through the exploration loop in Step 2, not specified by the user here.

## Exploration-First Principle

> The user's answers here are a **starting point**, not a complete specification. Schema types and relationships are *discovered* through iterative exploration in Step 2. The user does NOT need to provide a detailed Schema at setup time. If the user is unsure about entity types or relationships, proceed with just the domain and task — the exploration loop will discover them.

## Process

1. **Greet the user** and explain the 5-step construction process. Emphasize that they only need a high-level intent; details are discovered during exploration.
2. **Ask the 3-4 core questions** below (in order). Q3 and Q4 are optional.
3. **Save results** to the `User Concerns` section of `CLAUDE.md`.

## Questions to Ask

Keep it short. Ask at most these four questions; do NOT drill into properties, inheritance hierarchies, directional/temporal constraints, or update-frequency details.

### Q1 — Domain (required)
- What domain or industry are you building this knowledge graph for? (e.g., supply chain, semiconductor, healthcare, finance)

### Q2 — Primary Task/Purpose (required)
- What is the primary task or purpose of this KG? (e.g., risk monitoring, competitive intelligence, research synthesis)

### Q3 — Approximate Entity & Relationship Types (optional)
- What are the approximate entity types and relationship types you care about? (e.g., "companies, products, suppliers" and "supplies, partners with")
- **If the user is unsure, say "not sure" — proceed with just the domain and task. The exploration loop will discover them. Treat the user's answer as hints, not constraints.**

### Q4 — Specific Risk Concerns (optional)
- Any specific risk concerns you want monitored? (e.g., supply chain disruption, regulatory changes, competitor moves)
- If none, proceed — risk monitoring can be configured later.

> **Do NOT ask** about: detailed entity properties, inheritance hierarchies, relationship properties, directional/temporal constraints, or update-frequency specifics. These are discovered during exploration, not fixed at setup.

## Output Format

After collecting answers, write to `CLAUDE.md`:

```markdown
## User Concerns
- Concern: <one-line summary of the user's primary concern>
  - Domain: <domain>
  - Task: <primary task/purpose>
  - Entity types (approximate, optional): <list or "to be discovered">
  - Relationship types (approximate, optional): <list or "to be discovered">
  - Risk concerns (optional): <risk concerns or "none specified">
```

## Verification
- Confirm with the user that the summary is accurate.
- Remind them that the detailed Schema will be *discovered* during Step 2 exploration — they do not need to finalize it now.
- Ask if they want to add anything before proceeding to Step 2.