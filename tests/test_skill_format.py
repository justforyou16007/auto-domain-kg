"""Tests that all skills follow the Anthropic standard SKILL.md format.

The Anthropic standard format requires:
1. Each skill in its own directory
2. A SKILL.md file inside each skill directory
3. YAML frontmatter with at minimum `name` and `description` fields
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Root of the repository
REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# All 13 skills with their expected directory paths
EXPECTED_SKILL_DIRS = [
    "worker/socratic_inquiry",
    "worker/schema_creation",
    "worker/entity_collection",
    "worker/schema_refinement",
    "worker/triple_extraction",
    "worker/graph_persistence",
    "verifier/schema_audit",
    "verifier/graph_structure_audit",
    "verifier/graphrag_validation",
    "verifier/evidence_audit",
    "verifier/task_relevance_audit",
    "updater/daily_update",
    "risk/risk_assessment",
]

# Expected name and description for each skill (used in frontmatter validation)
EXPECTED_SKILL_METADATA: dict[str, dict[str, str]] = {
    "socratic_inquiry": {
        "name": "socratic-inquiry",
        "description": "Step 1 of KG construction. Ask structured Socratic questions to extract user concerns, domain scope, entity types, relationships, risk concerns, and update frequency. Save results to CLAUDE.md.",
    },
    "schema_creation": {
        "name": "schema-creation",
        "description": "Step 2 of KG construction (iterative). Research domain topics and generate schema definitions in iterations. Each iteration: search a sub-topic → create partial entity types and relationship types → merge results into tmp/schema_definition.json. Loop until no new schema types emerge or domain scope is exhausted.",
    },
    "entity_collection": {
        "name": "entity-collection",
        "description": "Part of iterative Step 2 of KG construction. During each schema iteration, search for entity-related news and articles, collecting evidence with source URLs. Evidence is collected incrementally per iteration, saved to data/evidence/.",
    },
    "schema_refinement": {
        "name": "schema-refinement",
        "description": "Part of iterative Step 2 of KG construction. After each iteration's entity collection, refine the partial schema based on collected evidence. Perform cross-iteration consistency checks: detect duplicate entity types, resolve relationship conflicts, ensure schema coherence.",
    },
    "triple_extraction": {
        "name": "triple-extraction",
        "description": "Extract entity-relation triples (subject, predicate, object) from collected news evidence. Save entities and relationships to markdown, save evidence slices with provenance to data/evidence/.",
    },
    "graph_persistence": {
        "name": "graph-persistence",
        "description": "Step 4 of KG construction. Persist schema, entities, and relationships to Neo4j. Link entity nodes to their schema nodes. Store evidence slices and source URLs on nodes for traceability.",
    },
    "schema_audit": {
        "name": "schema-audit",
        "description": "Verifier skill. Audit domain schema for completeness, consistency, proper inheritance, and no redundancy. Report issues with severity, category, and fix suggestions.",
    },
    "graph_structure_audit": {
        "name": "graph-structure-audit",
        "description": "Verifier skill. Audit the knowledge graph structure for connectivity, orphan nodes, relationship integrity, and graph health metrics.",
    },
    "graphrag_validation": {
        "name": "graphrag-validation",
        "description": "Verifier skill. Validate graph quality by asking domain-driven GraphRAG questions using Neo4j vector search and Cypher multi-hop queries. Check if the graph can answer user concerns.",
    },
    "evidence_audit": {
        "name": "evidence-audit",
        "description": "Verifier skill. Audit entity and relationship evidence for multi-source consistency. Verify that evidence slices match source URLs and that facts are corroborated across sources.",
    },
    "task_relevance_audit": {
        "name": "task-relevance-audit",
        "description": "Verifier skill. Evaluate whether the schema and graph instances remain relevant to the user's original concerns. Identify drift and suggest refocusing.",
    },
    "daily_update": {
        "name": "daily-update",
        "description": "Daily update flow. Search for today's news about graph entities, determine if schema or instance updates are needed, and send relevant news to the worker agent for graph updates.",
    },
    "risk_assessment": {
        "name": "risk-assessment",
        "description": "Risk assessment skill. An agent walks the graph to assess risk impact on user concerns, considering alternative paths, redundancy, and centrality. Risk is user-concern-driven, not auto-propagated.",
    },
}


def _get_skill_name_from_dir(skill_dir: str) -> str:
    """Extract the short skill name from a directory path like 'worker/socratic_inquiry'."""
    return Path(skill_dir).name


def _parse_yaml_frontmatter(skill_md_path: Path) -> dict[str, str] | None:
    """Parse YAML frontmatter from a SKILL.md file. Returns None if no valid frontmatter found."""
    content = skill_md_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None
    result: dict[str, str] = {}
    for line in lines[1:end_idx]:
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
    return result


class TestSkillDirectoryFormat:
    """Test that skills follow the Anthropic standard directory format."""

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_directory_exists(self, skill_rel_dir: str) -> None:
        """Each skill must have its own directory."""
        skill_dir = SKILLS_DIR / skill_rel_dir
        assert skill_dir.is_dir(), f"Skill directory not found: {skill_dir}"

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_md_file_exists(self, skill_rel_dir: str) -> None:
        """Each skill directory must contain a SKILL.md file."""
        skill_md = SKILLS_DIR / skill_rel_dir / "SKILL.md"
        assert skill_md.is_file(), f"SKILL.md not found in {skill_rel_dir}"

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_md_has_yaml_frontmatter(self, skill_rel_dir: str) -> None:
        """Each SKILL.md must have YAML frontmatter."""
        skill_md = SKILLS_DIR / skill_rel_dir / "SKILL.md"
        frontmatter = _parse_yaml_frontmatter(skill_md)
        assert frontmatter is not None, (
            f"No YAML frontmatter found in {skill_md}"
        )

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_md_has_name_field(self, skill_rel_dir: str) -> None:
        """Each SKILL.md must have a 'name' field in frontmatter."""
        skill_md = SKILLS_DIR / skill_rel_dir / "SKILL.md"
        frontmatter = _parse_yaml_frontmatter(skill_md)
        assert frontmatter is not None
        assert "name" in frontmatter, (
            f"Missing 'name' field in frontmatter of {skill_md}"
        )
        assert isinstance(frontmatter["name"], str) and len(frontmatter["name"]) > 0

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_md_has_description_field(self, skill_rel_dir: str) -> None:
        """Each SKILL.md must have a 'description' field in frontmatter."""
        skill_md = SKILLS_DIR / skill_rel_dir / "SKILL.md"
        frontmatter = _parse_yaml_frontmatter(skill_md)
        assert frontmatter is not None
        assert "description" in frontmatter, (
            f"Missing 'description' field in frontmatter of {skill_md}"
        )
        assert isinstance(frontmatter["description"], str) and len(frontmatter["description"]) > 0


class TestSkillMetadataAccuracy:
    """Test that the frontmatter metadata matches expected values."""

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_name_matches_expected(self, skill_rel_dir: str) -> None:
        """The frontmatter 'name' must match the expected kebab-case name."""
        skill_name = _get_skill_name_from_dir(skill_rel_dir)
        expected = EXPECTED_SKILL_METADATA[skill_name]
        skill_md = SKILLS_DIR / skill_rel_dir / "SKILL.md"
        frontmatter = _parse_yaml_frontmatter(skill_md)
        assert frontmatter is not None
        assert frontmatter["name"] == expected["name"], (
            f"Expected name '{expected['name']}' for {skill_rel_dir}, "
            f"got '{frontmatter['name']}'"
        )

    @pytest.mark.parametrize("skill_rel_dir", EXPECTED_SKILL_DIRS)
    def test_skill_description_matches_expected(self, skill_rel_dir: str) -> None:
        """The frontmatter 'description' must match the expected description."""
        skill_name = _get_skill_name_from_dir(skill_rel_dir)
        expected = EXPECTED_SKILL_METADATA[skill_name]
        skill_md = SKILLS_DIR / skill_rel_dir / "SKILL.md"
        frontmatter = _parse_yaml_frontmatter(skill_md)
        assert frontmatter is not None
        assert frontmatter["description"] == expected["description"], (
            f"Expected description for {skill_rel_dir} does not match.\n"
            f"  Expected: {expected['description']}\n"
            f"  Got:      {frontmatter['description']}"
        )


class TestOldFlatFilesRemoved:
    """Test that the old flat .md files have been deleted."""

    OLD_FLAT_PATHS = [
        "skills/worker/socratic_inquiry.md",
        "skills/worker/schema_creation.md",
        "skills/worker/entity_collection.md",
        "skills/worker/schema_refinement.md",
        "skills/worker/triple_extraction.md",
        "skills/worker/graph_persistence.md",
        "skills/verifier/schema_audit.md",
        "skills/verifier/graph_structure_audit.md",
        "skills/verifier/graphrag_validation.md",
        "skills/verifier/evidence_audit.md",
        "skills/verifier/task_relevance_audit.md",
        "skills/updater/daily_update.md",
        "skills/risk/risk_assessment.md",
    ]

    @pytest.mark.parametrize("old_path", OLD_FLAT_PATHS)
    def test_old_flat_md_file_deleted(self, old_path: str) -> None:
        """Old flat .md files must not exist anymore."""
        full_path = REPO_ROOT / old_path
        assert not full_path.exists(), (
            f"Old flat .md file still exists: {full_path}"
        )


class TestReferenceFormat:
    """Test that references in key docs point to the new SKILL.md paths."""

    DOCS_TO_CHECK = [
        "CLAUDE.md",
        "README.md",
        "README.zh.md",
    ]

    @pytest.mark.parametrize("doc", DOCS_TO_CHECK)
    def test_no_old_flat_path_references(self, doc: str) -> None:
        """Key docs must not contain old flat .md path references."""
        doc_path = REPO_ROOT / doc
        if not doc_path.exists():
            pytest.skip(f"{doc} not found")
        content = doc_path.read_text(encoding="utf-8")
        for skill_rel_dir in EXPECTED_SKILL_DIRS:
            skill_name = _get_skill_name_from_dir(skill_rel_dir)
            old_path = f"skills/{skill_rel_dir}.md"
            # Allow the old path only if it's a substring of the new path
            # e.g. "skills/worker/socratic_inquiry.md" is NOT a substring of
            # "skills/worker/socratic_inquiry/SKILL.md"
            # But we should be careful: check for exact old path references
            if old_path in content:
                # Check it's not part of the new path reference
                lines = content.split("\n")
                for line in lines:
                    if old_path in line and f"{old_path}/" not in line:
                        pytest.fail(
                            f"Found old flat path reference '{old_path}' in {doc}: {line.strip()}"
                        )