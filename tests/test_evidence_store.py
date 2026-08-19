"""Tests for the evidence store module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from auto_domain_kg.evidence_store import EvidenceRecord, EvidenceStore


@pytest.fixture
def store():
    """Create an EvidenceStore with a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EvidenceStore(base_dir=tmpdir)
        yield store


def test_save_and_load_evidence(store):
    """Test saving and loading evidence records."""
    record = EvidenceRecord(
        entity_id="entity-1",
        text_slice="Test Corp is a supplier of components.",
        source_url="https://example.com/news/1",
        source_title="Test News",
        timestamp="2026-01-01T00:00:00Z",
    )
    store.save_evidence(record)

    loaded = store.load_evidence_by_entity("entity-1")
    assert len(loaded) == 1
    assert loaded[0].entity_id == "entity-1"
    assert loaded[0].text_slice == "Test Corp is a supplier of components."
    assert loaded[0].source_url == "https://example.com/news/1"


def test_save_and_load_relation_evidence(store):
    """Test saving and loading evidence for a relation."""
    record = EvidenceRecord(
        entity_id="entity-1",
        relation_id="rel-1",
        text_slice="Entity A supplies Entity B.",
        source_url="https://example.com/news/2",
    )
    store.save_evidence(record)

    loaded = store.load_evidence_by_relation("rel-1")
    assert len(loaded) == 1
    assert loaded[0].relation_id == "rel-1"


def test_load_nonexistent_entity(store):
    """Test loading evidence for a nonexistent entity."""
    loaded = store.load_evidence_by_entity("nonexistent")
    assert loaded == []


def test_save_evidence_batch(store):
    """Test saving multiple evidence records."""
    records = [
        EvidenceRecord(
            entity_id="entity-1",
            text_slice="Fact 1",
            source_url="https://example.com/1",
        ),
        EvidenceRecord(
            entity_id="entity-1",
            text_slice="Fact 2",
            source_url="https://example.com/2",
        ),
        EvidenceRecord(
            entity_id="entity-2",
            text_slice="Fact 3",
            source_url="https://example.com/3",
        ),
    ]
    store.save_evidence_batch(records)

    entity1_evidence = store.load_evidence_by_entity("entity-1")
    assert len(entity1_evidence) == 2

    entity2_evidence = store.load_evidence_by_entity("entity-2")
    assert len(entity2_evidence) == 1


def test_load_all_evidence(store):
    """Test loading all evidence records."""
    records = [
        EvidenceRecord(
            entity_id="entity-1",
            text_slice="Fact 1",
            source_url="https://example.com/1",
        ),
        EvidenceRecord(
            entity_id="entity-2",
            text_slice="Fact 2",
            source_url="https://example.com/2",
        ),
    ]
    store.save_evidence_batch(records)

    all_evidence = store.load_all_evidence()
    assert len(all_evidence) == 2


def test_delete_evidence(store):
    """Test deleting evidence files."""
    record = EvidenceRecord(
        entity_id="entity-1",
        text_slice="Test",
        source_url="https://example.com",
    )
    store.save_evidence(record)
    assert len(store.load_evidence_by_entity("entity-1")) == 1

    store.delete_evidence("entity-1")
    assert len(store.load_evidence_by_entity("entity-1")) == 0


def test_count_evidence_records(store):
    """Test counting evidence records."""
    records = [
        EvidenceRecord(
            entity_id="entity-1",
            text_slice="Fact 1",
            source_url="https://example.com/1",
        ),
        EvidenceRecord(
            entity_id="entity-1",
            text_slice="Fact 2",
            source_url="https://example.com/2",
        ),
    ]
    store.save_evidence_batch(records)
    assert store.count_evidence_records() == 2


def test_get_stats(store):
    """Test getting evidence store statistics."""
    records = [
        EvidenceRecord(
            entity_id="entity-1",
            text_slice="Fact 1",
            source_url="https://example.com/1",
        ),
        EvidenceRecord(
            entity_id="entity-1",
            relation_id="rel-1",
            text_slice="Fact 2",
            source_url="https://example.com/2",
        ),
    ]
    store.save_evidence_batch(records)

    stats = store.get_stats()
    assert stats["entity_count"] == 1
    assert stats["relation_count"] == 1
    assert stats["total_records"] == 2


def test_evidence_record_provenance():
    """Test that evidence records have provenance tracking."""
    record = EvidenceRecord(
        entity_id="entity-1",
        text_slice="Test",
        source_url="https://example.com",
    )
    assert record.retrieved_at is not None
    assert "T" in record.retrieved_at  # ISO format timestamp


def test_jsonl_format(store):
    """Test that evidence is stored in JSONL format."""
    record = EvidenceRecord(
        entity_id="entity-1",
        text_slice="Test",
        source_url="https://example.com",
    )
    store.save_evidence(record)

    # Read the raw file to verify JSONL format
    file_path = store._entity_path("entity-1")
    with open(file_path, "r") as f:
        lines = f.readlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["entity_id"] == "entity-1"
    assert parsed["text_slice"] == "Test"