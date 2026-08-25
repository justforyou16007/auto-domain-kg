"""Acceptance tests for Issue #15: audit rubrics configuration module.

Tests RubricsConfig (load default, load from file, save, get enabled,
set strictness) and RubricItem defaults.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_domain_kg.audit_rubrics import RubricItem, RubricsConfig


# The 5 audit skills the rubrics must cover.
EXPECTED_AUDIT_SKILLS = [
    "schema_audit",
    "graph_structure_audit",
    "graphrag_validation",
    "evidence_audit",
    "task_relevance_audit",
]


class TestRubricItem:
    def test_rubric_item_fields(self) -> None:
        item = RubricItem(
            name="schema_audit",
            description="Audit schema",
            strictness_level="strict",
            enabled=True,
            custom_thresholds={"max_missing_entity_types": 0},
        )
        assert item.name == "schema_audit"
        assert item.strictness_level == "strict"
        assert item.enabled is True
        assert item.custom_thresholds["max_missing_entity_types"] == 0


class TestRubricsConfigDefault:
    def test_load_default_returns_config(self) -> None:
        cfg = RubricsConfig.load_default()
        assert isinstance(cfg, RubricsConfig)

    def test_default_has_all_five_skills(self) -> None:
        cfg = RubricsConfig.load_default()
        names = {r.name for r in cfg.get_enabled_rubrics()}
        assert names == set(EXPECTED_AUDIT_SKILLS)

    def test_default_strictness_is_strict(self) -> None:
        cfg = RubricsConfig.load_default()
        for r in cfg.get_enabled_rubrics():
            assert r.strictness_level == "strict", (
                f"{r.name} should default to strict"
            )

    def test_default_strict_thresholds(self) -> None:
        cfg = RubricsConfig.load_default()
        thresholds = {r.name: r.custom_thresholds for r in cfg.get_enabled_rubrics()}
        assert thresholds["schema_audit"]["max_missing_entity_types"] == 0
        assert thresholds["schema_audit"]["max_undefined_relationships"] == 0
        assert thresholds["graph_structure_audit"]["max_orphan_entities"] == 0
        assert thresholds["graph_structure_audit"]["min_avg_relationships"] == 1.0
        assert thresholds["graphrag_validation"]["min_answerable_ratio"] == 0.8
        assert thresholds["graphrag_validation"]["min_precision"] == "medium"
        assert thresholds["evidence_audit"]["min_sources_per_entity"] == 2
        assert thresholds["evidence_audit"]["min_sources_per_critical"] == 3
        assert thresholds["task_relevance_audit"]["min_fully_covered_ratio"] == 0.7


class TestRubricsConfigFileIO:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        cfg = RubricsConfig.load_default()
        out = tmp_path / "rubrics.yaml"
        cfg.save_to_file(out)
        assert out.is_file()
        loaded = RubricsConfig.load_from_file(out)
        assert isinstance(loaded, RubricsConfig)
        names = {r.name for r in loaded.get_enabled_rubrics()}
        assert names == set(EXPECTED_AUDIT_SKILLS)
        # thresholds preserved
        th = {r.name: r.custom_thresholds for r in loaded.get_enabled_rubrics()}
        assert th["schema_audit"]["max_missing_entity_types"] == 0

    def test_load_from_json_file(self, tmp_path: Path) -> None:
        import json

        data = {
            "rubrics": [
                {
                    "name": "schema_audit",
                    "description": "d",
                    "strictness_level": "strict",
                    "enabled": True,
                    "custom_thresholds": {"max_missing_entity_types": 0},
                }
            ]
        }
        p = tmp_path / "rubrics.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        loaded = RubricsConfig.load_from_file(p)
        assert isinstance(loaded, RubricsConfig)
        enabled = loaded.get_enabled_rubrics()
        assert len(enabled) == 1
        assert enabled[0].name == "schema_audit"


class TestRubricsConfigSetStrictness:
    def test_set_strictness_moderate(self) -> None:
        cfg = RubricsConfig.load_default()
        cfg.set_strictness("moderate")
        for r in cfg.get_enabled_rubrics():
            assert r.strictness_level == "moderate"

    def test_set_strictness_invalid_raises(self) -> None:
        cfg = RubricsConfig.load_default()
        with pytest.raises(ValueError):
            cfg.set_strictness("bogus")


class TestRubricsConfigEnabled:
    def test_get_enabled_excludes_disabled(self) -> None:
        cfg = RubricsConfig.load_default()
        # Disable one rubric and ensure it is excluded.
        cfg.rubrics[0].enabled = False
        disabled_name = cfg.rubrics[0].name
        enabled_names = {r.name for r in cfg.get_enabled_rubrics()}
        assert disabled_name not in enabled_names
