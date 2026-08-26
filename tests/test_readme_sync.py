"""Acceptance tests for Issue #11: README sync with the actual codebase.

After Issues #4, #6, #7, #9, #10 the codebase gained source provenance
fields, multi-source cross-validation, Schema/Instance layer separation,
schema hierarchy (SUBCLASS_OF), and hierarchy-aware merging. These tests
assert that BOTH README files (README.md and README.zh.md) document those
features, using the English method/term names that the constraints require
to be retained verbatim in both language versions.
"""

from __future__ import annotations

from pathlib import Path

import re
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README_EN = REPO_ROOT / "README.md"
README_ZH = REPO_ROOT / "README.zh.md"
SKILLS_DIR = REPO_ROOT / "skills"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing README: {path}"
    return path.read_text(encoding="utf-8")


# Method / term names that MUST appear in BOTH README files. These map
# directly to the gaps called out in Issue #11 and are required (per the
# task constraints) to keep their English originals in both languages.
REQUIRED_IN_BOTH = [
    # Issue #6: source provenance fields
    "source_url",
    "source_text",
    # Issue #9: evidence_store cross-validation methods
    "get_source_urls",
    "get_source_count",
    "cross_validate",
    "is_well_supported",
    # Issue #10: neo4j_client schema hierarchy methods
    "create_schema_hierarchy",
    "get_schema_ancestors",
    "get_schema_descendants",
    "find_common_ancestor",
    "get_schema_with_ancestors",
    # Issues #9, #10: graph_ops hierarchy-aware merge methods
    "find_merge_target_with_hierarchy",
    "merge_entity_to_parent_schema",
    # Issue #7: Schema/Instance layer + SUBCLASS_OF
    "SUBCLASS_OF",
    "HAS_SCHEMA",
]


@pytest.mark.parametrize("term", REQUIRED_IN_BOTH)
def test_en_readme_documents_term(term: str) -> None:
    """English README must document each required method/term."""
    assert term in _read(README_EN), (
        f"README.md is missing required term '{term}'"
    )


@pytest.mark.parametrize("term", REQUIRED_IN_BOTH)
def test_zh_readme_documents_term(term: str) -> None:
    """Chinese README must document each required method/term (English originals kept)."""
    assert term in _read(README_ZH), (
        f"README.zh.md is missing required term '{term}'"
    )


def test_en_readme_has_schema_instance_section() -> None:
    """English README must have a Schema/Instance Layer Separation section."""
    assert "Schema/Instance Layer Separation" in _read(README_EN)


def test_zh_readme_has_schema_instance_section() -> None:
    """Chinese README must reference Schema/Instance separation (English terms kept)."""
    assert "Schema/Instance" in _read(README_ZH)


def test_en_readme_test_count_is_eleven() -> None:
    """English README must report 11 test files (translation + readme_sync added)."""
    en = _read(README_EN)
    assert "pytest tests (11 files)" in en, (
        "README.md Project Structure does not report 11 test files"
    )
    assert "pytest tests (9 files)" not in en, (
        "README.md still reports 9 test files"
    )
    assert "pytest tests (7 files)" not in en, (
        "README.md still reports 7 test files"
    )


def test_zh_readme_test_count_is_eleven() -> None:
    """Chinese README must report 11 test files (translation + readme_sync added)."""
    zh = _read(README_ZH)
    assert "pytest 测试文件（11 个）" in zh, (
        "README.zh.md Project Structure does not report 11 test files"
    )
    assert "pytest 测试文件（9 个）" not in zh, (
        "README.zh.md still reports 9 test files"
    )
    assert "pytest 测试文件（7 个）" not in zh, (
        "README.zh.md still reports 7 test files"
    )


def test_readmes_document_translation_module() -> None:
    """Both READMEs must document the translation.py module (synced with code)."""
    en = _read(README_EN)
    zh = _read(README_ZH)
    assert "### `translation.py`" in en, (
        "README.md is missing the translation.py module section"
    )
    assert "TranslationClient" in en, (
        "README.md does not mention TranslationClient"
    )
    assert "### `translation.py`" in zh, (
        "README.zh.md is missing the translation.py module section"
    )
    assert "TranslationClient" in zh, (
        "README.zh.md does not mention TranslationClient"
    )


def test_readmes_document_bilingual_search_methods() -> None:
    """Both READMEs must document the news_adapter bilingual/translate methods."""
    en = _read(README_EN)
    zh = _read(README_ZH)
    for method in ("bilingual_search", "bilingual_search_and_translate", "translate_content"):
        assert method in en, (
            f"README.md does not document news_adapter method '{method}'"
        )
        assert method in zh, (
            f"README.zh.md does not document news_adapter method '{method}'"
        )


def test_readmes_list_translation_py_in_structure() -> None:
    """Both READMEs must list translation.py in the project structure tree."""
    en = _read(README_EN)
    zh = _read(README_ZH)
    assert "translation.py" in en, (
        "README.md project structure does not list translation.py"
    )
    assert "translation.py" in zh, (
        "README.zh.md project structure does not list translation.py"
    )


def test_readmes_have_documentation_sync_rule_section() -> None:
    """Both READMEs must have a Documentation Sync Rule section (Issue #29)."""
    en = _read(README_EN)
    zh = _read(README_ZH)
    assert "## Documentation Sync Rule" in en, (
        "README.md is missing the '## Documentation Sync Rule' section"
    )
    assert "tests/test_readme_sync.py" in en, (
        "README.md Documentation Sync Rule does not reference tests/test_readme_sync.py"
    )
    assert "## 文档同步规则" in zh, (
        "README.zh.md is missing the '## 文档同步规则' section"
    )
    assert "tests/test_readme_sync.py" in zh, (
        "README.zh.md 文档同步规则 does not reference tests/test_readme_sync.py"
    )


def test_readmes_mention_completeness_gap() -> None:
    """Both READMEs must mention completeness gap discovery in the flow."""
    en = _read(README_EN)
    zh = _read(README_ZH)
    assert "completeness gap" in en.lower() or "Completeness Gap" in en, (
        "README.md does not mention completeness gap discovery"
    )
    assert "完整性缺口" in zh or "completeness gap" in zh.lower(), (
        "README.zh.md does not mention completeness gap discovery"
    )


# ---------------------------------------------------------------------------
# Issue #28: formal skill files must not contain issue-tracker references.
# ---------------------------------------------------------------------------
_ISSUE_REF_RE = re.compile(r"(Issue #|issue #|closes #|fixes #|resolves #)", re.IGNORECASE)


def _collect_skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def test_skills_contain_no_issue_references() -> None:
    """No SKILL.md file under skills/ may reference an issue tracker id.

    Regression guard for Issue #28: formal skill files must not contain
    expressions like ``(Issue #25)`` / ``closes #`` / ``fixes #``.
    """
    offenders: list[str] = []
    for skill_file in _collect_skill_files():
        text = skill_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if _ISSUE_REF_RE.search(line):
                offenders.append(f"{skill_file}:{line_no}: {line.strip()}")
    assert not offenders, (
        "Issue-tracker references remain in skill files (Issue #28):\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# Issue #29 Part A: documentation must reflect the actual codebase.
# ---------------------------------------------------------------------------


def test_readmes_document_neo4j_keyword_and_bm25_search() -> None:
    """Both READMEs must document neo4j_client keyword_search/bm25_search.

    The codebase implements `Neo4jClient.keyword_search()` and
    `Neo4jClient.bm25_search()`; documentation must reflect this.
    """
    en = _read(README_EN)
    zh = _read(README_ZH)
    for method in ("keyword_search", "bm25_search"):
        assert method in en, (
            f"README.md does not document neo4j_client method '{method}'"
        )
        assert method in zh, (
            f"README.zh.md does not document neo4j_client method '{method}'"
        )


def test_claude_md_daily_update_has_cross_validation() -> None:
    """CLAUDE.md Daily Update Flow must mention multi-source cross-validation.

    The daily_update skill requires cross-validation before updating the graph,
    so CLAUDE.md must reflect this step.
    """
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "Cross-validate" in text, (
        "CLAUDE.md Daily Update Flow does not mention cross-validation"
    )


def test_claude_md_daily_update_has_hierarchy_merging() -> None:
    """CLAUDE.md Daily Update Flow must mention hierarchy-aware merging.

    The daily_update skill uses hierarchy-aware Schema merging
    (`merge_entity_to_parent_schema`), so CLAUDE.md must reflect this.
    """
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "hierarchy-aware Schema merging" in text, (
        "CLAUDE.md Daily Update Flow does not mention hierarchy-aware merging"
    )


# ---------------------------------------------------------------------------
# Issue #29 Part B: the Documentation Sync Rule section must exist.
# ---------------------------------------------------------------------------


def test_en_readme_has_documentation_sync_rule() -> None:
    """English README must contain the '## Documentation Sync Rule' section."""
    en = _read(README_EN)
    assert "## Documentation Sync Rule" in en, (
        "README.md is missing the '## Documentation Sync Rule' section"
    )
    assert "tests/test_readme_sync.py" in en, (
        "README.md Documentation Sync Rule must reference tests/test_readme_sync.py"
    )


def test_zh_readme_has_documentation_sync_rule() -> None:
    """Chinese README must contain the '## 文档同步规则' section."""
    zh = _read(README_ZH)
    assert "## 文档同步规则" in zh, (
        "README.zh.md is missing the '## 文档同步规则' section"
    )
    assert "tests/test_readme_sync.py" in zh, (
        "README.zh.md 文档同步规则 must reference tests/test_readme_sync.py"
    )
