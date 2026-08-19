# Socratic Inquiry — Step 1: Extract User Concerns

## Goal
Understand what the user wants from the knowledge graph by asking structured Socratic questions.

## Process

1. **Greet the user** and explain the 6-step construction process.
2. **Ask questions** in the order below, adapting follow-ups based on answers.
3. **Save results** to the `User Concerns` section of `CLAUDE.md`.

## Questions to Ask

### Domain
- What domain or industry are you building this knowledge graph for? (e.g., supply chain, healthcare, finance, research)
- What is the primary purpose of this KG? (e.g., risk monitoring, competitive intelligence, research synthesis)

### Entities
- What are the key entity types in your domain? (e.g., companies, people, products, events)
- For each entity type, what properties would you like to track? (e.g., name, description, location, status)
- Are there any entity hierarchies or inheritance relationships? (e.g., "Company is a type of Organization")

### Relationships
- What are the key relationships between entities? (e.g., "supplies", "acquires", "partners with")
- Are there any directional or temporal constraints on relationships?
- Should relationships carry properties (e.g., contract_value, start_date)?

### Risk Concerns
- What risk concerns do you have? (e.g., supply chain disruption, regulatory changes, competitor moves)
- What entities are most critical to your risk monitoring?
- What would trigger a risk alert for you?

### Update Frequency
- How often should the knowledge graph be updated? (daily, weekly, monthly)
- Would you like automated daily news scanning for entity updates?

## Output Format

After collecting answers, write to `CLAUDE.md`:

```markdown
## User Concerns
- Concern: <summary of user's primary concern>
  - Domain: <domain>
  - Entities: <entity type list>
  - Relationships: <relationship type list>
  - Risk concerns: <risk concerns>
  - Update frequency: <frequency>
```

## Verification
- Confirm with the user that the summary is accurate.
- Ask if they want to add anything before proceeding to Step 2.