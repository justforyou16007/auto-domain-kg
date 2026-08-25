"""Audit rubrics configuration module (Issue #15).

Provides user-customizable audit rubrics that drive the 5 verifier audit
skills. Rubrics carry a strictness level and per-skill strict thresholds.
The default configuration is the **strictest** level so that any error-level
issue blocks an adversarial round from passing.

Default rubrics map to the 5 existing audit skills:
    schema_audit, graph_structure_audit, graphrag_validation,
    evidence_audit, task_relevance_audit
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Valid strictness levels, from most to least strict.
STRICTNESS_LEVELS: tuple[str, ...] = ("strict", "moderate", "lenient")

# Default rubric definitions: one entry per audit skill, each with the
# strict thresholds mandated by the issue spec.
DEFAULT_RUBRICS: list[dict[str, Any]] = [
    {
        "name": "schema_audit",
        "description": (
            "Audit domain schema for completeness, consistency, inheritance, "
            "and no redundancy."
        ),
        "strictness_level": "strict",
        "enabled": True,
        "custom_thresholds": {
            "max_missing_entity_types": 0,
            "max_undefined_relationships": 0,
        },
    },
    {
        "name": "graph_structure_audit",
        "description": (
            "Audit the knowledge graph structure for connectivity, orphan "
            "nodes, relationship integrity, and graph health metrics."
        ),
        "strictness_level": "strict",
        "enabled": True,
        "custom_thresholds": {
            "max_orphan_entities": 0,
            "min_avg_relationships": 1.0,
        },
    },
    {
        "name": "graphrag_validation",
        "description": (
            "Validate graph quality by asking domain-driven GraphRAG "
            "questions and checking the graph can answer them."
        ),
        "strictness_level": "strict",
        "enabled": True,
        "custom_thresholds": {
            "min_answerable_ratio": 0.8,
            "min_precision": "medium",
        },
    },
    {
        "name": "evidence_audit",
        "description": (
            "Audit entity and relationship evidence for multi-source "
            "consistency, quality, and provenance."
        ),
        "strictness_level": "strict",
        "enabled": True,
        "custom_thresholds": {
            "min_sources_per_entity": 2,
            "min_sources_per_critical": 3,
        },
    },
    {
        "name": "task_relevance_audit",
        "description": (
            "Evaluate whether the schema and graph instances remain relevant "
            "to the user's original concerns."
        ),
        "strictness_level": "strict",
        "enabled": True,
        "custom_thresholds": {
            "min_fully_covered_ratio": 0.7,
        },
    },
]


@dataclass
class RubricItem:
    """A single audit rubric with strictness and thresholds."""

    name: str
    description: str
    strictness_level: str = "strict"
    enabled: bool = True
    custom_thresholds: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.strictness_level not in STRICTNESS_LEVELS:
            raise ValueError(
                f"Invalid strictness_level '{self.strictness_level}'. "
                f"Must be one of {STRICTNESS_LEVELS}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (for YAML/JSON)."""
        return {
            "name": self.name,
            "description": self.description,
            "strictness_level": self.strictness_level,
            "enabled": self.enabled,
            "custom_thresholds": dict(self.custom_thresholds),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RubricItem":
        """Construct a RubricItem from a plain dict."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            strictness_level=data.get("strictness_level", "strict"),
            enabled=data.get("enabled", True),
            custom_thresholds=dict(data.get("custom_thresholds", {})),
        )


class RubricsConfig:
    """A collection of audit rubrics that drive the verifier audits."""

    def __init__(self, rubrics: list[RubricItem] | None = None) -> None:
        """Initialize the config.

        Args:
            rubrics: List of RubricItem. If None, starts empty.
        """
        self.rubrics: list[RubricItem] = list(rubrics) if rubrics else []

    @classmethod
    def load_default(cls) -> "RubricsConfig":
        """Load the default rubrics (all strict, all enabled)."""
        return cls(rubrics=[RubricItem.from_dict(r) for r in DEFAULT_RUBRICS])

    @classmethod
    def load_from_file(cls, path: str | Path) -> "RubricsConfig":
        """Load custom rubrics from a YAML or JSON file.

        The file must contain a top-level ``rubrics`` key holding a list of
        rubric definitions. Missing fields fall back to defaults.

        Args:
            path: Path to a .yaml/.yml/.json file.

        Returns:
            A RubricsConfig populated from the file.
        """
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)

        rubric_list = data.get("rubrics", []) if isinstance(data, dict) else []
        return cls(
            rubrics=[RubricItem.from_dict(r) for r in rubric_list]
        )

    def save_to_file(self, path: str | Path) -> None:
        """Save the current config to a YAML or JSON file.

        Args:
            path: Output path. Extension determines format (.yaml/.yml/.json).
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {"rubrics": [r.to_dict() for r in self.rubrics]}
        if p.suffix.lower() in (".yaml", ".yml"):
            p.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
        else:
            p.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    def get_enabled_rubrics(self) -> list[RubricItem]:
        """Return only the enabled rubrics, preserving order."""
        return [r for r in self.rubrics if r.enabled]

    def set_strictness(self, level: str) -> None:
        """Set all rubrics to a strictness level.

        Args:
            level: One of "strict", "moderate", "lenient".

        Raises:
            ValueError: If level is invalid.
        """
        if level not in STRICTNESS_LEVELS:
            raise ValueError(
                f"Invalid strictness level '{level}'. "
                f"Must be one of {STRICTNESS_LEVELS}"
            )
        for r in self.rubrics:
            r.strictness_level = level

    def to_dict(self) -> dict[str, Any]:
        """Serialize the whole config to a plain dict."""
        return {"rubrics": [r.to_dict() for r in self.rubrics]}
