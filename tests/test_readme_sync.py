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

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README_EN = REPO_ROOT / "README.md"
README_ZH = REPO_ROOT / "README.zh.md"


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


def test_en_readme_test_count_is_seven() -> None:
    """English README must report 9 test files (audit_report + audit_rubrics added)."""
    en = _read(README_EN)
    assert "pytest tests (9 files)" in en, (
        "README.md Project Structure does not report 9 test files"
    )
    assert "pytest tests (7 files)" not in en, (
        "README.md still reports 7 test files"
    )


def test_zh_readme_test_count_is_seven() -> None:
    """Chinese README must report 9 test files (audit_report + audit_rubrics added)."""
    zh = _read(README_ZH)
    assert "pytest 测试文件（9 个）" in zh, (
        "README.zh.md Project Structure does not report 9 test files"
    )
    assert "pytest 测试文件（7 个）" not in zh, (
        "README.zh.md still reports 7 test files"
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
