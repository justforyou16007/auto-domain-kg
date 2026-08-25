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

    def get_source_urls(
        self, entity_id: str, relation_id: str = ""
    ) -> list[str]:
        """Get all unique source URLs for an entity or relation.

        Args:
            entity_id: Entity identifier.
            relation_id: Optional relation identifier. If provided, sources
                        for the relation are returned instead.

        Returns:
            Deduplicated list of source URLs.
        """
        if relation_id:
            records = self.load_evidence_by_relation(relation_id)
        else:
            records = self.load_evidence_by_entity(entity_id)

        sources: list[str] = []
        seen: set[str] = set()
        for r in records:
            url = r.source_url.strip()
            if url and url not in seen:
                seen.add(url)
                sources.append(url)
        return sources

    def get_source_count(
        self, entity_id: str, relation_id: str = ""
    ) -> int:
        """Count the number of independent sources for an entity or relation.

        Args:
            entity_id: Entity identifier.
            relation_id: Optional relation identifier. If provided, sources
                        for the relation are counted instead.

        Returns:
            Number of unique source URLs.
        """
        return len(self.get_source_urls(entity_id, relation_id))

    @staticmethod
    def _detect_conflicts(
        texts_by_source: dict[str, list[str]],
        source_keywords: dict[str, set[str]],
        common_keywords: set[str],
    ) -> bool:
        """Detect contradictory statements across sources.

        A conflict is identified when a content keyword shared by multiple
        sources is **affirmed** by at least one source and **negated** by
        another. Negation is detected by looking for negation markers
        ("not", "no", "never", "denies", "refuted", ...) appearing within a
        small window before the keyword in one source but not in another.

        Args:
            texts_by_source: Mapping of source URL to its text slices.
            source_keywords: Mapping of source URL to the set of content
                keywords extracted from that source.
            common_keywords: Content keywords shared across all sources.

        Returns:
            True if a contradictory (differing negation polarity) statement
            is found, False otherwise.
        """
        negation_markers = {
            "not", "no", "never", "nor", "none", "cannot", "neither",
            "denies", "denied", "refuted", "disputes", "contradicts",
            "false", "untrue", "wrong",
        }

        # Precompute, for each source, the set of keywords that are negated
        # (a negation marker appears within 3 words before the keyword).
        negated_by_source: dict[str, set[str]] = {}
        for url, texts in texts_by_source.items():
            negated: set[str] = set()
            for text in texts:
                words = [
                    w.strip(".,!?;:\"'()[]{}").lower()
                    for w in text.split()
                ]
                for i, word in enumerate(words):
                    if not word or word not in common_keywords:
                        continue
                    window = words[max(0, i - 3):i]
                    if any(w in negation_markers for w in window):
                        negated.add(word)
            negated_by_source[url] = negated

        # A conflict exists if some shared keyword is negated in one source
        # but affirmed (present but not negated) in another.
        sources = list(negated_by_source.keys())
        for keyword in common_keywords:
            negated_in = [s for s in sources if keyword in negated_by_source[s]]
            affirmed_in = [
                s for s in sources
                if keyword in source_keywords.get(s, set())
                and s not in negated_in
            ]
            if negated_in and affirmed_in:
                return True
        return False

    def cross_validate(
        self, entity_id: str, relation_id: str = ""
    ) -> dict:
        """Cross-validate evidence for an entity or relation across sources.

        Checks whether multiple sources agree on key facts by comparing
        text slices. Sources are considered conflicting if they contain
        contradictory statements about the same fact.

        Args:
            entity_id: Entity identifier.
            relation_id: Optional relation identifier. If provided, the
                        relation's evidence is validated instead.

        Returns:
            Dictionary with:
                has_consensus: True if sources generally agree.
                source_count: Number of independent sources.
                sources: List of unique source URLs.
                conflicting: True if contradictory evidence was found.
                details: Human-readable description of the validation result.
        """
        if relation_id:
            records = self.load_evidence_by_relation(relation_id)
        else:
            records = self.load_evidence_by_entity(entity_id)

        source_urls = self.get_source_urls(entity_id, relation_id)
        source_count = len(source_urls)

        if source_count == 0:
            return {
                "has_consensus": False,
                "source_count": 0,
                "sources": [],
                "conflicting": False,
                "details": "No evidence found for this entity/relation.",
            }

        if source_count == 1:
            return {
                "has_consensus": False,
                "source_count": 1,
                "sources": source_urls,
                "conflicting": False,
                "details": (
                    "Single source only. At least 2 independent sources "
                    "are recommended for reliable evidence."
                ),
            }

        # Group text slices by source URL
        texts_by_source: dict[str, list[str]] = {}
        for r in records:
            url = r.source_url.strip()
            if url:
                texts_by_source.setdefault(url, []).append(r.text_slice)

        # Simple consensus check: look for common keywords across sources
        source_keywords: dict[str, set[str]] = {}
        for url, texts in texts_by_source.items():
            keywords: set[str] = set()
            for t in texts:
                for word in t.lower().split():
                    if len(word) >= 3 and not word.isdigit():
                        keywords.add(word.strip(".,!?;:\"'()[]{}"))
            source_keywords[url] = keywords

        # Check for keyword overlap across sources
        url_list = list(texts_by_source.keys())
        if len(url_list) >= 2:
            common_keywords = source_keywords[url_list[0]].copy()
            for url in url_list[1:]:
                common_keywords &= source_keywords[url]

            # Detect contradictory statements across sources. A conflict is
            # flagged when the same content keyword is affirmed by one source
            # and negated by another (different negation polarity).
            conflicting = self._detect_conflicts(
                texts_by_source, source_keywords, common_keywords
            )

            has_consensus = len(common_keywords) >= 3 and not conflicting
            details = (
                f"Multiple sources ({source_count}) found. "
                f"Sources share {len(common_keywords)} common keywords. "
            )
            if conflicting:
                details += (
                    "Sources contain contradictory statements — flag for "
                    "human review."
                )
            elif has_consensus:
                details += "Evidence is consistent across sources."
            else:
                details += (
                    "Limited keyword overlap — sources may cover "
                    "different aspects of the same entity."
                )
        else:
            has_consensus = False
            conflicting = False
            details = "Single source only."

        return {
            "has_consensus": has_consensus,
            "source_count": source_count,
            "sources": source_urls,
            "conflicting": conflicting,
            "details": details,
        }

    def is_well_supported(
        self,
        entity_id: str,
        relation_id: str = "",
        min_sources: int = 2,
    ) -> bool:
        """Check if an entity or relation is supported by enough sources.

        Args:
            entity_id: Entity identifier.
            relation_id: Optional relation identifier. If provided, checks
                        the relation's evidence instead.
            min_sources: Minimum number of independent sources required
                        (default 2).

        Returns:
            True if the number of unique sources >= min_sources.
        """
        return self.get_source_count(entity_id, relation_id) >= min_sources