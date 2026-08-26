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

# All 15 skills with their expected directory paths
EXPECTED_SKILL_DIRS = [
    "worker/socratic_inquiry",
    "worker/kg_gen_pipeline",
    "worker/schema_creation",
    "worker/schema_merge",
    "worker/evidence_search",
    "worker/triple_extraction",
    "worker/entity_relation_merge",
    "worker/subgraph_merge",
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
        "description": "Step 1 of KG construction. Ask a small number of Socratic questions to capture the user's domain, primary task, approximate entity/relationship types, and risk concerns. The user does NOT need to provide a detailed Schema — Schema is discovered through exploration in Step 2, not fixed at setup time. Save results to CLAUDE.md.",
    },
    "schema_creation": {
        "name": "schema-creation",
        "description": "Step 2 of the KG pipeline (parallel proposal). GraphRAG search existing Neo4j Schema (vector search + multi-hop) to find related Schema, then based on search results + model's own domain knowledge create concept-level Schema entity types and relationship types. Schema only models concept-level types — never concrete instance names. Schema relationships must have explicit business semantics. Bilingual (zh+en) queries are searched and results translated before schema creation. Cache the proposal locally (tmp/schema_proposals/agent_N.json) and notify the main Agent. ONLY creates Schema + Relations — no entity collection, triple extraction, refinement, or persistence.",
    },
    "schema_merge": {
        "name": "schema-merge",
        "description": "Step 3 of the KG pipeline. Merge multiple Schema proposals (from Step 2's N parallel sub-agents) with existing Neo4j Schema into one global Schema. Maintain the SUBCLASS_OF hierarchy (e.g. Car → EV → Xiaomi Auto). Detect duplicates, resolve conflicts, ensure a concept-level-only ontology. Uses neo4j_client.create_schema_hierarchy(), get_schema_ancestors(), find_common_ancestor(). Output merged global Schema to tmp/schema_definition.json.",
    },
    "evidence_search": {
        "name": "evidence-search",
        "description": "Step 4a of the KG pipeline. Deep-research-style evidence search. Multi-round iterative: each round generates zh+en queries → bilingual_search() top-k=20 → merge by URL → translate_content() to zh-CN → analyze findings → generate next-round questions → continue. Does NOT stop after finding one piece of evidence — goal is comprehensive coverage. Stop when a round produces no new facts. Uses news_adapter.bilingual_search() and translation.TranslationClient.translate_content(). Saves evidence to data/evidence/.",
    },
    "triple_extraction": {
        "name": "triple-extraction",
        "description": "Step 4b of the KG pipeline (per Schema/Relation dimension). From the Schema/Relation's leaf entities, explore outward X-hop (default 3) and extract entities and relations along Schema-defined Relation directions. Form a subgraph centered on the leaf entity; each entity and relation carries an evidence slice + source_url. Validate entity-relation against schema-relation alignment and flag triples needing schema extension. X is configurable (default 3) — X-hop exploration is performed explicitly. Only extract concrete Instance entities (never concepts).",
    },
    "entity_relation_merge": {
        "name": "entity-relation-merge",
        "description": "Step 4c of the KG pipeline. Entity alignment and subgraph merging across sources. Semantic judgment identifies the same entity across sources (e.g. 苹果 ↔ Apple). Merge subgraphs. Bind entities to Schema nodes via HAS_SCHEMA. Mark entities with no matching Schema as empty Schema for later Schema creation. Uses graph_ops.find_merge_target_with_hierarchy() and merge_entity_to_parent_schema().",
    },
    "subgraph_merge": {
        "name": "subgraph-merge",
        "description": "Step 5 of the KG pipeline. Take the Neo4j intersection 2-hop subgraph of newly inserted entities and merge overlapping subgraphs. For entities with empty Schema, create new Schema nodes and route through schema-merge. For new Schema, trigger Step 4 recursively. Stop condition: new search entities are completely irrelevant to user's domain concerns (no butterfly effect — only direct domain relevance counts). Uses graph_ops.multi_hop_subgraph() and vector_search().",
    },
    "kg_gen_pipeline": {
        "name": "kg-gen-pipeline",
        "description": "Main orchestration skill for the 6-step deep-research multi-agent KG construction pipeline. Uses Paseo MCP spawn_agent to dispatch parallel sub-agents at each phase: Step 1 Socratic Inquiry, Step 2 parallel schema_creation sub-agents, Step 3 schema-merge, Step 4 per-Schema evidence-search + triple_extraction + entity-relation-merge, Step 5 subgraph-merge, Step 6 audit-fix loop. Defines stop conditions, parallel dispatch, and error handling.",
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
        "description": "Verifier skill. Audit entity and relationship evidence for multi-source consistency using code-level cross-validation. Verify that evidence slices match source URLs, that facts are corroborated across sources, and flag single-source or conflicting evidence. Use EvidenceStore.cross_validate() and is_well_supported() for automated checks.",
    },
    "task_relevance_audit": {
        "name": "task-relevance-audit",
        "description": "Verifier skill. Evaluate whether the schema and graph instances remain relevant to the user's original concerns. Identify drift and suggest refocusing.",
    },
    "daily_update": {
        "name": "daily-update",
        "description": "Daily update flow. Search for today's news about graph entities, determine if schema or instance updates are needed, and send relevant news to the worker agent for graph updates. When risk events are detected, trigger the full 6-step risk analysis pipeline (risk_assessment skill).",
    },
    "risk_assessment": {
        "name": "risk-assessment",
        "description": "6-step news-to-graph impact analysis pipeline. 1) Receive Daily News 2) Extract News Events 3) Associate Evidence Fragments 4) GraphRAG Event-to-Node Analysis 5) DAG Impact Tracing 6) Generate Impact Report using external template. Risk is user-concern-driven, not auto-propagated.",
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
        "skills/worker/kg_gen_pipeline.md",
        "skills/worker/schema_creation.md",
        "skills/worker/schema_merge.md",
        "skills/worker/evidence_search.md",
        "skills/worker/triple_extraction.md",
        "skills/worker/entity_relation_merge.md",
        "skills/worker/subgraph_merge.md",
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