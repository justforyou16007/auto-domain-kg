"""Evidence storage module for saving and loading evidence slices with provenance.

Evidence is stored as JSONL files in the data/evidence/ directory.
Each record contains the entity/relation ID, text slice, source URL, and timestamps.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class EvidenceRecord:
    """A single evidence record with provenance tracking."""

    entity_id: str
    text_slice: str
    source_url: str
    source_title: str = ""
    timestamp: str = ""
    relation_id: str = ""
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EvidenceStore:
    """Store and retrieve evidence slices with provenance.

    Evidence is stored as JSONL files in a configurable directory
    (default: data/evidence/). Each file is named by entity_id or
    relation_id for easy lookup.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        """Initialize the evidence store.

        Args:
            base_dir: Base directory for evidence storage.
                      Defaults to "data/evidence" relative to cwd.
        """
        self._base_dir = Path(base_dir or os.environ.get(
            "EVIDENCE_DIR", "data/evidence"
        ))
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _entity_path(self, entity_id: str) -> Path:
        """Get the file path for evidence related to an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            Path to the entity's evidence file.
        """
        safe_name = entity_id.replace("/", "_").replace(":", "_")
        return self._base_dir / f"entity_{safe_name}.jsonl"

    def _relation_path(self, relation_id: str) -> Path:
        """Get the file path for evidence related to a relation.

        Args:
            relation_id: Relation identifier.

        Returns:
            Path to the relation's evidence file.
        """
        safe_name = relation_id.replace("/", "_").replace(":", "_")
        return self._base_dir / f"rel_{safe_name}.jsonl"

    def save_evidence(self, record: EvidenceRecord) -> None:
        """Save an evidence record to disk.

        Args:
            record: The evidence record to save.
        """
        file_path = self._entity_path(record.entity_id)
        if record.relation_id:
            file_path = self._relation_path(record.relation_id)

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def save_evidence_batch(self, records: list[EvidenceRecord]) -> None:
        """Save multiple evidence records in batch.

        Args:
            records: List of evidence records to save.
        """
        for record in records:
            self.save_evidence(record)

    def load_evidence_by_entity(
        self, entity_id: str
    ) -> list[EvidenceRecord]:
        """Load all evidence records for a given entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            List of EvidenceRecord objects.
        """
        file_path = self._entity_path(entity_id)
        return self._load_file(file_path)

    def load_evidence_by_relation(
        self, relation_id: str
    ) -> list[EvidenceRecord]:
        """Load all evidence records for a given relation.

        Args:
            relation_id: Relation identifier.

        Returns:
            List of EvidenceRecord objects.
        """
        file_path = self._relation_path(relation_id)
        return self._load_file(file_path)

    def _load_file(self, file_path: Path) -> list[EvidenceRecord]:
        """Load evidence records from a JSONL file.

        Args:
            file_path: Path to the JSONL file.

        Returns:
            List of EvidenceRecord objects.
        """
        if not file_path.exists():
            return []

        records: list[EvidenceRecord] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        records.append(EvidenceRecord(**data))
                    except (json.JSONDecodeError, TypeError) as e:
                        # Skip malformed lines
                        continue

        return records

    def load_all_evidence(self) -> list[EvidenceRecord]:
        """Load all evidence records from the store.

        Returns:
            List of all EvidenceRecord objects.
        """
        records: list[EvidenceRecord] = []
        for file_path in self._base_dir.glob("*.jsonl"):
            records.extend(self._load_file(file_path))
        return records

    def delete_evidence(self, entity_id: str, relation_id: str = "") -> None:
        """Delete evidence files for an entity or relation.

        Args:
            entity_id: Entity identifier.
            relation_id: Optional relation identifier. If provided, only
                        relation evidence is deleted.
        """
        if relation_id:
            file_path = self._relation_path(relation_id)
        else:
            file_path = self._entity_path(entity_id)

        if file_path.exists():
            file_path.unlink()

    def count_evidence_records(self) -> int:
        """Count total evidence records across all files.

        Returns:
            Total number of evidence records.
        """
        count = 0
        for file_path in self._base_dir.glob("*.jsonl"):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
        return count

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the evidence store.

        Returns:
            Dictionary with entity_count, relation_count, and total_records.
        """
        entities: set[str] = set()
        relations: set[str] = set()
        total = 0

        for file_path in self._base_dir.glob("*.jsonl"):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        total += 1
                        try:
                            data = json.loads(line)
                            if data.get("entity_id"):
                                entities.add(data["entity_id"])
                            if data.get("relation_id"):
                                relations.add(data["relation_id"])
                        except json.JSONDecodeError:
                            continue

        return {
            "entity_count": len(entities),
            "relation_count": len(relations),
            "total_records": total,
        }